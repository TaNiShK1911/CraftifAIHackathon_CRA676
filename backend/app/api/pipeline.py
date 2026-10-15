"""
api/pipeline.py — GET/POST /api/pipeline/runs
Pipeline run precision/speed comparison table (values from PipeGen's speed report).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import PipelineRunRow
from app.schemas import PipelineRunCreate, PipelineRunRead

router = APIRouter()


@router.get("/pipeline/runs", response_model=list[PipelineRunRead])
def list_runs(session: Session = Depends(get_session)) -> list[PipelineRunRow]:
    return list(session.exec(select(PipelineRunRow).order_by(PipelineRunRow.created_at.desc())).all())  # type: ignore[arg-type]


@router.post("/pipeline/runs", response_model=PipelineRunRead, status_code=201)
def create_run(
    body: PipelineRunCreate,
    session: Session = Depends(get_session),
) -> PipelineRunRow:
    row = PipelineRunRow(**body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
