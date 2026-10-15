"""
api/events.py — GET /api/events
Lists recent canonical events from the DB with optional filters.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import EventRow
from app.schemas import EventRead

router = APIRouter()


@router.get("/events", response_model=list[EventRead])
def list_events(
    limit: int = Query(default=50, le=200),
    since: Optional[datetime] = Query(default=None),
    label: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[EventRow]:
    stmt = select(EventRow)
    if since:
        stmt = stmt.where(EventRow.ts >= since)
    if label:
        stmt = stmt.where(EventRow.label == label)
    stmt = stmt.order_by(EventRow.ts.desc()).limit(limit)  # type: ignore[arg-type]
    return list(session.exec(stmt).all())
