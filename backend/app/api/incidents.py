"""
api/incidents.py — GET/PATCH /api/incidents[/{id}] + GET /api/incidents/{id}/events
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.bus import bus
from app.db import get_session
from app.models import EventRow, IncidentRow
from app.schemas import IncidentPatch, IncidentRead, IncidentStatus

router = APIRouter()


@router.get("/incidents", response_model=list[IncidentRead])
def list_incidents(
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[IncidentRow]:
    stmt = select(IncidentRow)
    if status:
        stmt = stmt.where(IncidentRow.status == status.upper())
    if type:
        stmt = stmt.where(IncidentRow.type == type.upper())
    stmt = stmt.order_by(IncidentRow.last_seen.desc()).limit(limit)  # type: ignore[arg-type]
    return list(session.exec(stmt).all())


@router.get("/incidents/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: int,
    session: Session = Depends(get_session),
) -> IncidentRow:
    inc = session.get(IncidentRow, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.get("/incidents/{incident_id}/events")
def get_incident_events(
    incident_id: int,
    session: Session = Depends(get_session),
) -> list[dict]:
    """
    Return events associated with a specific incident.
    Links by (source_id, track_id, zone_id) from the incident row,
    filtered to events within the incident's time window.
    Frontend expects: { id, incident_id, ts, confidence }
    """
    inc = session.get(IncidentRow, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    stmt = select(EventRow).where(
        EventRow.source_id == inc.source_id,
        EventRow.ts >= inc.first_seen,
        EventRow.ts <= inc.last_seen,
    )
    if inc.track_id is not None:
        stmt = stmt.where(EventRow.track_id == inc.track_id)
    if inc.zone_id is not None:
        stmt = stmt.where(EventRow.zone_id == inc.zone_id)

    stmt = stmt.order_by(EventRow.ts.asc()).limit(100)  # type: ignore[arg-type]
    rows = session.exec(stmt).all()

    return [
        {
            "id": row.id,
            "incident_id": incident_id,
            "ts": row.ts.isoformat() if row.ts else None,
            "confidence": row.confidence,
        }
        for row in rows
    ]


@router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def patch_incident(
    incident_id: int,
    body: IncidentPatch,
    session: Session = Depends(get_session),
) -> IncidentRow:
    inc = session.get(IncidentRow, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if body.status is not None:
        inc.status = body.status.value
        if body.status == IncidentStatus.ACKNOWLEDGED:
            inc.ack_by = body.ack_by or "operator"
            inc.ack_at = datetime.now(timezone.utc)
    session.add(inc)
    session.commit()
    session.refresh(inc)

    await bus.publish(
        "incident.updated",
        {
            "id": inc.id,
            "status": inc.status,
            "ack_by": inc.ack_by,
        },
    )
    return inc
