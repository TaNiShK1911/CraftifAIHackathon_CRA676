"""
api/health.py — GET /api/health
Returns broker connection status, last message age, dropped count, DB ok,
active thresholds and (stub) FPS.

Response matches the frontend's Health interface:
  { status, mqtt_connected, last_message_age_s, dropped, fps, thresholds }
"""
from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import settings
from app.ingest import mqtt_consumer

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    mqtt_state = mqtt_consumer.state
    last_ts = mqtt_state.get("last_message_ts")
    age: float | None = None
    if last_ts is not None:
        age = round(time.monotonic() - last_ts, 1)

    return {
        "status": "ok",
        "mqtt_connected": mqtt_state.get("connected", False),
        "last_message_age_s": age,
        "dropped": mqtt_state.get("dropped_messages", 0),
        "fps": None,  # filled by PipeGen's live report; optional
        "thresholds": {
            "min_consecutive_frames": settings.min_consecutive_frames,
            "quiet_seconds": settings.quiet_seconds,
            "loiter_seconds": settings.loiter_seconds,
            "event_throttle_ms": settings.event_throttle_ms,
        },
        "db": "ok",
    }
