"""
api/stats.py — GET /api/stats/summary and /api/stats/timeseries

Response shapes match the frontend interfaces:
  StatsSummary: { open, today, high_critical, mtta_seconds, by_type, fps }
  TimeseriesPoint: { ts, count }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select, text

from app.db import get_session
from app.ingest import mqtt_consumer
from app.models import EventRow, IncidentRow

router = APIRouter()


@router.get("/stats/summary")
def stats_summary(session: Session = Depends(get_session)) -> dict:
    import time as _time

    now_utc = datetime.now(timezone.utc)
    start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    # Open incidents
    open_count: int = session.exec(
        select(func.count(IncidentRow.id)).where(IncidentRow.status == "OPEN")
    ).one()  # type: ignore[arg-type]

    # Today's incidents
    today_count: int = session.exec(
        select(func.count(IncidentRow.id)).where(IncidentRow.first_seen >= start_of_day)
    ).one()  # type: ignore[arg-type]

    # High + Critical count
    high_crit: int = session.exec(
        select(func.count(IncidentRow.id)).where(
            IncidentRow.severity.in_(["HIGH", "CRITICAL"])  # type: ignore[attr-defined]
        )
    ).one()  # type: ignore[arg-type]

    # Mean time to acknowledge (seconds) — only for acknowledged incidents
    acked_rows = session.exec(
        select(IncidentRow.first_seen, IncidentRow.ack_at).where(
            IncidentRow.ack_at.is_not(None)  # type: ignore[union-attr]
        )
    ).all()
    mtta: float | None = None
    if acked_rows:
        deltas = [
            (ack_at - first_seen).total_seconds()
            for first_seen, ack_at in acked_rows
            if ack_at and first_seen
        ]
        mtta = sum(deltas) / len(deltas) if deltas else None

    # By type
    type_rows = session.exec(
        select(IncidentRow.type, func.count(IncidentRow.id)).group_by(IncidentRow.type)  # type: ignore[arg-type]
    ).all()
    by_type = {row[0]: row[1] for row in type_rows}

    return {
        "open": open_count,
        "open_incidents": open_count,
        "today": today_count,
        "total_incidents": today_count,
        "high_critical": high_crit,
        "mtta_seconds": mtta,
        "by_type": by_type,
        "fps": None,  # filled by PipeGen's live metrics
    }


@router.get("/stats/timeseries")
def stats_timeseries(
    minutes: int = Query(default=60, description="Look-back window in minutes"),
    bucket: str = Query(default="1m", description="Bucket size: 1m, 5m, 15m, 1h"),
    window: Optional[str] = Query(default=None, description="Look-back window string (e.g. 60m)"),
    session: Session = Depends(get_session),
) -> list[dict]:
    # Parse bucket to seconds
    _bucket_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
    bucket_s = _bucket_map.get(bucket, 60)

    # window param takes precedence if provided
    if window:
        _window_map = {"60m": 3600, "6h": 21600, "24h": 86400}
        window_s = _window_map.get(window, minutes * 60)
    else:
        window_s = minutes * 60

    since = datetime.now(timezone.utc) - timedelta(seconds=window_s)

    # SQLite strftime-based bucketing
    rows = session.exec(
        text(
            f"""
            SELECT
                datetime(strftime('%s', first_seen) / {bucket_s} * {bucket_s}, 'unixepoch') AS bucket,
                COUNT(*) AS cnt
            FROM incidents
            WHERE first_seen >= :since
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        ).bindparams(since=since.isoformat())
    ).all()

    # Frontend expects { ts, count } per point
    return [{"ts": r[0], "count": r[1]} for r in rows]
