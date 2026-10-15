"""
api/evidence.py — GET/POST /api/evidence
List or upload evidence files (IR graph screenshots, speed reports, etc.).

Frontend expects: { id, kind, url, caption }
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, select
from typing import Optional

from app.db import get_session
from app.models import EvidenceRow

router = APIRouter()

_EVIDENCE_DIR = Path("data/evidence")
_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _to_response(row: EvidenceRow) -> dict:
    """Convert DB row to the shape the frontend expects."""
    url = f"/media/evidence/{Path(row.file_path).name}" if row.file_path else ""
    return {
        "id": row.id,
        "kind": row.kind,
        "url": url,
        "caption": row.description or row.title,
        "title": row.title,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "file_path": row.file_path,
        "description": row.description,
    }


@router.get("/evidence")
def list_evidence(
    kind: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    stmt = select(EvidenceRow)
    if kind:
        stmt = stmt.where(EvidenceRow.kind == kind)
    stmt = stmt.order_by(EvidenceRow.created_at.desc())  # type: ignore[arg-type]
    rows = list(session.exec(stmt).all())
    return [_to_response(r) for r in rows]


@router.post("/evidence", status_code=201)
async def upload_evidence(
    kind: str = Form(...),
    title: str = Form(...),
    description: str = Form(default=""),
    file: UploadFile = File(default=None),
    session: Session = Depends(get_session),
) -> dict:
    file_path: str | None = None
    if file and file.filename:
        dest = _EVIDENCE_DIR / file.filename
        with open(dest, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        file_path = str(dest)

    row = EvidenceRow(
        kind=kind,
        title=title,
        description=description or None,
        file_path=file_path,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_response(row)
