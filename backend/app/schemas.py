"""
schemas.py — Pydantic v2 canonical schemas used across ingest, rules and API layers.
The adapter converts raw PipeGen output into CanonicalEvent; everything else depends only on this shape.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class IncidentType(str, Enum):
    ZONE_INTRUSION = "ZONE_INTRUSION"
    PPE_VIOLATION = "PPE_VIOLATION"
    LOITERING = "LOITERING"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


# ---------------------------------------------------------------------------
# Canonical event (adapter output)
# ---------------------------------------------------------------------------

class CanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_id: str                          # camera / stream id e.g. "cam0"
    frame_id: int | None = None
    track_id: int | None = None             # tracker id if PipeGen tracking enabled
    label: str                              # "person", "no_hardhat", "no_vest", ...
    confidence: float                       # 0..1
    bbox: tuple[float, float, float, float] | None = None  # x, y, w, h normalised 0..1
    zone_id: str | None = None              # set if PipeGen ROI/zone analytics reports it
    attributes: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    data_origin: str = "live"               # live | replay | seed


# ---------------------------------------------------------------------------
# Incident read schema (API response)
# ---------------------------------------------------------------------------

class IncidentRead(BaseModel):
    id: int
    type: IncidentType
    severity: Severity
    status: IncidentStatus
    source_id: str
    track_id: int | None
    zone_id: str | None
    first_seen: datetime
    last_seen: datetime
    event_count: int
    max_confidence: float
    snapshot_path: str | None
    ack_by: str | None
    ack_at: datetime | None
    data_origin: str = "live"

    model_config = {"from_attributes": True}


class IncidentPatch(BaseModel):
    status: IncidentStatus | None = None
    ack_by: str | None = None


# ---------------------------------------------------------------------------
# Event read schema (API response)
# ---------------------------------------------------------------------------

class EventRead(BaseModel):
    id: int
    ts: datetime
    source_id: str
    frame_id: int | None
    track_id: int | None
    label: str
    confidence: float
    bbox_json: str | None
    zone_id: str | None
    data_origin: str = "live"

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pipeline run (evidence / precision comparison)
# ---------------------------------------------------------------------------

class PipelineRunCreate(BaseModel):
    model_name: str
    precision: str           # "FP32" | "FP16" | "INT8"
    engine_path: str | None = None
    fps: float | None = None
    latency_ms: float | None = None
    power_w: float | None = None
    accuracy_map: float | None = None
    notes: str | None = None
    data_origin: str = "live"


class PipelineRunRead(PipelineRunCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class EvidenceRead(BaseModel):
    id: int
    created_at: datetime
    kind: str
    title: str
    file_path: str | None
    description: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class StatsSummary(BaseModel):
    total_events: int
    total_incidents: int
    open_incidents: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    last_hour_incidents: int
    broker_connected: bool
    last_message_age_s: float | None
    dropped_messages: int


class TimeseriesPoint(BaseModel):
    bucket: datetime
    count: int


# ---------------------------------------------------------------------------
# SSE messages
# ---------------------------------------------------------------------------

class SSEMessage(BaseModel):
    event: str
    data: dict[str, Any]
