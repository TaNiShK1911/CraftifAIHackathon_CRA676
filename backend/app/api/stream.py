"""
api/stream.py — GET /api/stream  (Server-Sent Events)

Clients connect once and receive live incident events pushed by the rules engine.
Heartbeat `: ping` every 15 s keeps proxies alive.
The frontend reconnects automatically on disconnect.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.bus import bus
from app.config import settings

router = APIRouter()


async def _event_generator():
    q = bus.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=float(settings.sse_heartbeat_seconds))
                event_name = msg["event"]
                data = json.dumps(msg["data"])
                yield f"event: {event_name}\ndata: {data}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat to keep proxy connections alive
                yield ": ping\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        bus.unsubscribe(q)


@router.get("/stream")
async def sse_stream():
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
