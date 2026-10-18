"""
models.py — SQLModel table definitions for SQLite.
Uses SQLite WAL mode (set in db.py) so the API can read while ingest writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class EventRow(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(index=True)
    source_id: str
    frame_id: Optional[int] = None
    track_id: Optional[int] = None
    label: str
    confidence: float
    bbox_json: Optional[str] = None       # JSON string "[x, y, w, h]" normalised
    zone_id: Optional[str] = None
    raw_json: Optional[str] = None        # original payload for audit/debug
    data_origin: str = Field(default="live", index=True)  # live | replay | seed


class IncidentRow(SQLModel, table=True):
    __tablename__ = "incidents"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True)
    severity: str
    status: str = Field(default="OPEN", index=True)
    source_id: str
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    first_seen: datetime = Field(index=True)
    last_seen: datetime
    event_count: int = Field(default=1)
    max_confidence: float = Field(default=0.0)
    snapshot_path: Optional[str] = None
    ack_by: Optional[str] = None
    ack_at: Optional[datetime] = None
    data_origin: str = Field(default="live", index=True)  # live | replay | seed


class PipelineRunRow(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_name: str
    precision: str           # FP32 | FP16 | INT8
    engine_path: Optional[str] = None
    fps: Optional[float] = None
    latency_ms: Optional[float] = None
    power_w: Optional[float] = None
    accuracy_map: Optional[float] = None
    notes: Optional[str] = None
    data_origin: str = Field(default="live", index=True)  # live | replay | seed


class EvidenceRow(SQLModel, table=True):
    __tablename__ = "evidence"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: str                # "screenshot" | "speed_report" | "video" | etc.
    title: str
    file_path: Optional[str] = None
    description: Optional[str] = None
