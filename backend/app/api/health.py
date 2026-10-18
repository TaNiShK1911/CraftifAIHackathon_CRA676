"""
api/health.py — GET /api/health
Returns broker connection status, last message age, dropped count, DB ok,
active thresholds, and counts by data_origin.

Response matches the frontend's Health interface:
  { status, mqtt_connected, last_message_age_s, dropped, thresholds, counts_by_origin }
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.config import settings
from app.db import get_session
from app.ingest import mqtt_consumer
from app.models import EventRow, IncidentRow

router = APIRouter()


@router.get("/health")
async def health(session: Session = Depends(get_session)) -> dict:
    mqtt_state = mqtt_consumer.state
    last_ts = mqtt_state.get("last_message_ts")
    age: float | None = None
    if last_ts is not None:
        age = round(time.monotonic() - last_ts, 1)

    # Count events and incidents by data_origin
    event_origin_rows = session.exec(
        select(EventRow.data_origin, func.count(EventRow.id)).group_by(EventRow.data_origin)  # type: ignore[arg-type]
    ).all()
    incident_origin_rows = session.exec(
        select(IncidentRow.data_origin, func.count(IncidentRow.id)).group_by(IncidentRow.data_origin)  # type: ignore[arg-type]
    ).all()
    events_by_origin = {row[0]: row[1] for row in event_origin_rows}
    incidents_by_origin = {row[0]: row[1] for row in incident_origin_rows}

    # Last live message age: use mqtt_consumer timestamp for live
    last_live_message_age_seconds: float | None = age

    return {
        "ok": True,
        "status": "ok",
        "mqtt_connected": mqtt_state.get("connected", False),
        "last_message_age_s": age,
        "last_live_message_age_seconds": last_live_message_age_seconds,
        "dropped": mqtt_state.get("dropped_messages", 0),
        "events_by_origin": events_by_origin,
        "incidents_by_origin": incidents_by_origin,
        "thresholds": {
            "min_consecutive_frames": settings.min_consecutive_frames,
            "quiet_seconds": settings.quiet_seconds,
            "loiter_seconds": settings.loiter_seconds,
            "event_throttle_ms": settings.event_throttle_ms,
        },
        "db": "ok",
    }
