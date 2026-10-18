"""
main.py — FastAPI application entry point.

Lifespan:
  1. Creates SQLite tables (WAL mode).
  2. Starts MQTT consumer background task.
  3. Starts JSON metadata tailer background task.
  4. Starts auto-close background task.

All perception is done by PipeGen. This file contains no inference code.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.ingest import adapter, mqtt_consumer, json_tailer
from app.rules import engine as rules_engine
from app.api import health, events, incidents, stats, stream, pipeline, evidence, zones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


async def _ingest_payload(payload: dict, *, data_origin: str = "live") -> None:
    """Shared callback: raw PipeGen payload → CanonicalEvent → rules engine."""
    canonical_events = adapter.normalize(payload)
    for event in canonical_events:
        event.data_origin = data_origin
        await rules_engine.handle(event)


async def _ingest_live(payload: dict) -> None:
    """MQTT and JSON tailer callback.
    Detects _data_origin injected by replay.py; defaults to 'live'.
    """
    origin = payload.pop("_data_origin", "live")
    await _ingest_payload(payload, data_origin=origin)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("SiteGuard backend starting up...")
    init_db()

    tasks = []

    # MQTT consumer
    tasks.append(asyncio.create_task(mqtt_consumer.run(_ingest_live), name="mqtt_consumer"))

    # JSON tailer
    tasks.append(asyncio.create_task(json_tailer.run(_ingest_live), name="json_tailer"))

    # Auto-close background task
    tasks.append(asyncio.create_task(rules_engine.auto_close_loop(), name="auto_close"))

    logger.info("Background tasks started: %s", [t.get_name() for t in tasks])

    yield

    # Shutdown
    logger.info("SiteGuard backend shutting down...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SiteGuard API",
    description=(
        "Workplace Safety Sentinel — ingests PipeGen MQTT/JSON output "
        "and turns per-frame detections into deduplicated safety incidents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

PREFIX = "/api"
app.include_router(health.router, prefix=PREFIX, tags=["health"])
app.include_router(events.router, prefix=PREFIX, tags=["events"])
app.include_router(incidents.router, prefix=PREFIX, tags=["incidents"])
app.include_router(stats.router, prefix=PREFIX, tags=["stats"])
app.include_router(stream.router, prefix=PREFIX, tags=["stream"])
app.include_router(pipeline.router, prefix=PREFIX, tags=["pipeline"])
app.include_router(evidence.router, prefix=PREFIX, tags=["evidence"])
app.include_router(zones.router, prefix=PREFIX, tags=["zones"])

# ---------------------------------------------------------------------------
# Static media (annotated video, snapshots, evidence images)
# ---------------------------------------------------------------------------

_data_dir = Path("data")
_data_dir.mkdir(exist_ok=True)
Path("data/evidence").mkdir(parents=True, exist_ok=True)
Path("data/snapshots").mkdir(parents=True, exist_ok=True)


# Serve the PipeGen annotated video at /media/video
# MEDIA_VIDEO_PATH may be an absolute path outside data/
@app.get("/media/video")
async def serve_video():
    from fastapi.responses import FileResponse
    candidates = [
        Path(settings.media_video_path),
        _data_dir / "annotated.mp4",
        Path("demo.mp4"),
        Path("../demo.mp4"),
    ]
    for video in candidates:
        if video.is_file():
            return FileResponse(str(video.resolve()), media_type="video/mp4")
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Annotated video not available")


# Mount /media for snapshots, evidence images, and other static data files
app.mount("/media", StaticFiles(directory=str(_data_dir), html=False), name="media")
