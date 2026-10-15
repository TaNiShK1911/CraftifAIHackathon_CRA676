"""
rules/engine.py — Converts a stream of CanonicalEvent objects into Incidents.

Algorithm (per section 7 of BACKEND_IMPLEMENTATION_PLAN.md):
  1. Classify each event into zero or more candidate IncidentTypes.
  2. Debounce: require min_consecutive_frames of the same condition before opening.
  3. Open / update incident in DB and push to SSE bus.
  4. Escalate: zone intrusion older than loiter_seconds → CRITICAL.
  5. Auto-close background task: resolve incidents with no new event for quiet_seconds.
  6. Throttle storage: persist only one raw event per (key, 500 ms).
  7. Deduplicate: same (source_id, frame_id, track_id, label) from MQTT and tailer.

State is kept in memory (dict keyed by IncidentKey). The DB is the durable store.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml
from sqlmodel import Session, select

from app.bus import bus
from app.config import settings
from app.db import get_engine
from app.models import EventRow, IncidentRow
from app.schemas import CanonicalEvent, IncidentType, Severity, IncidentStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dedup cache: prevent double-ingesting same frame from MQTT + tailer
# ---------------------------------------------------------------------------

_dedup_cache: dict[tuple, float] = {}   # key → monotonic time of last seen
_DEDUP_TTL = 2.0  # seconds


def _is_duplicate(event: CanonicalEvent) -> bool:
    key = (
        event.source_id,
        event.frame_id,
        event.track_id,
        event.label,
    )
    now = time.monotonic()
    if key in _dedup_cache and now - _dedup_cache[key] < _DEDUP_TTL:
        return True
    _dedup_cache[key] = now
    # GC old entries periodically
    if len(_dedup_cache) > 2000:
        cutoff = now - _DEDUP_TTL * 2
        dead = [k for k, t in _dedup_cache.items() if t < cutoff]
        for k in dead:
            del _dedup_cache[k]
    return False


# ---------------------------------------------------------------------------
# Incident state tracking
# ---------------------------------------------------------------------------

@dataclass
class IncidentKey:
    type: IncidentType
    source_id: str
    track_id: int | None
    zone_id: str | None

    def as_tuple(self) -> tuple:
        return (self.type, self.source_id, self.track_id, self.zone_id)


@dataclass
class IncidentState:
    key: IncidentKey
    incident_id: int
    severity: Severity
    first_seen: float    # monotonic
    last_seen: float     # monotonic
    debounce_count: int = 0
    open: bool = False
    # throttle storage: last time we persisted a raw event row
    last_stored: dict[str, float] = field(default_factory=dict)  # sub-key → monotonic

    def should_store_event(self, sub_key: str) -> bool:
        """Return True if enough time has elapsed to persist another event row."""
        now = time.monotonic()
        threshold = settings.event_throttle_ms / 1000.0
        if now - self.last_stored.get(sub_key, 0.0) >= threshold:
            self.last_stored[sub_key] = now
            return True
        return False


# In-memory registry of open + debouncing incidents
_states: dict[tuple, IncidentState] = {}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_zone_labels() -> list[str]:
    try:
        path = settings.adapter_yaml_path
        with open(path) as fh:
            cfg = yaml.safe_load(fh)
        return [lbl.lower() for lbl in cfg.get("zone_labels", ["person"])]
    except Exception:
        return ["person"]


def _load_ppe_labels() -> list[str]:
    try:
        path = settings.adapter_yaml_path
        with open(path) as fh:
            cfg = yaml.safe_load(fh)
        return [lbl.lower() for lbl in cfg.get("ppe_violation_labels", ["no_hardhat", "no_vest"])]
    except Exception:
        return ["no_hardhat", "no_vest", "no_helmet", "no_safety_vest"]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(event: CanonicalEvent) -> list[tuple[IncidentType, Severity]]:
    """Return list of (IncidentType, default_severity) for this event."""
    results: list[tuple[IncidentType, Severity]] = []
    label_lc = event.label.lower()

    zone_labels = _load_zone_labels()
    ppe_labels = _load_ppe_labels()

    # ZONE_INTRUSION: a zone_label inside a hazard zone
    if label_lc in zone_labels and event.zone_id:
        results.append((IncidentType.ZONE_INTRUSION, Severity.HIGH))

    # PPE_VIOLATION
    if label_lc in ppe_labels:
        results.append((IncidentType.PPE_VIOLATION, Severity.MEDIUM))

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def handle(event: CanonicalEvent) -> None:
    """Process one CanonicalEvent: classify, debounce, open/update incidents."""
    if _is_duplicate(event):
        return

    candidates = _classify(event)
    for incident_type, default_severity in candidates:
        key = IncidentKey(
            type=incident_type,
            source_id=event.source_id,
            track_id=event.track_id,
            zone_id=event.zone_id,
        )
        await _process_candidate(event, key, incident_type, default_severity)


async def _process_candidate(
    event: CanonicalEvent,
    key: IncidentKey,
    incident_type: IncidentType,
    default_severity: Severity,
) -> None:
    ktuple = key.as_tuple()
    now_mono = time.monotonic()

    if ktuple not in _states:
        # Start debounce
        _states[ktuple] = IncidentState(
            key=key,
            incident_id=-1,
            severity=default_severity,
            first_seen=now_mono,
            last_seen=now_mono,
            debounce_count=1,
        )
        return

    state = _states[ktuple]
    state.last_seen = now_mono
    state.debounce_count += 1

    if not state.open:
        # Still debouncing
        if state.debounce_count >= settings.min_consecutive_frames:
            # Open incident
            incident_id = await _open_incident(event, key, incident_type, default_severity)
            state.incident_id = incident_id
            state.open = True
        return

    # Incident already open — update it
    await _update_incident(state, event)

    # Escalation check: zone intrusion lingering → LOITERING
    if incident_type == IncidentType.ZONE_INTRUSION:
        duration = now_mono - state.first_seen
        if duration > settings.loiter_seconds and state.severity != Severity.CRITICAL:
            await _escalate(state, event)


async def _open_incident(
    event: CanonicalEvent,
    key: IncidentKey,
    incident_type: IncidentType,
    severity: Severity,
) -> int:
    now_utc = datetime.now(timezone.utc)
    row = IncidentRow(
        type=incident_type.value,
        severity=severity.value,
        status=IncidentStatus.OPEN.value,
        source_id=event.source_id,
        track_id=event.track_id,
        zone_id=event.zone_id,
        first_seen=now_utc,
        last_seen=now_utc,
        event_count=1,
        max_confidence=event.confidence,
        snapshot_path=event.attributes.get("snapshot_path"),
    )
    with Session(get_engine()) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        incident_id = row.id  # type: ignore[assignment]

    # Also store the triggering event row
    await _store_event(event)

    await bus.publish(
        "incident.opened",
        {
            "id": incident_id,
            "type": incident_type.value,
            "severity": severity.value,
            "source_id": event.source_id,
            "track_id": event.track_id,
            "zone_id": event.zone_id,
            "first_seen": now_utc.isoformat(),
        },
    )
    logger.info("Incident %d opened: %s (%s)", incident_id, incident_type.value, severity.value)
    return incident_id


async def _update_incident(state: IncidentState, event: CanonicalEvent) -> None:
    now_utc = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        inc = session.get(IncidentRow, state.incident_id)
        if inc is None:
            return
        inc.last_seen = now_utc
        inc.event_count = (inc.event_count or 0) + 1
        inc.max_confidence = max(inc.max_confidence or 0.0, event.confidence)
        session.add(inc)
        session.commit()

    sub_key = str(state.incident_id)
    if state.should_store_event(sub_key):
        await _store_event(event)

    await bus.publish(
        "incident.updated",
        {
            "id": state.incident_id,
            "event_count": 0,   # will be refreshed by FE on reconnect
            "last_seen": now_utc.isoformat(),
            "max_confidence": event.confidence,
        },
    )


async def _escalate(state: IncidentState, event: CanonicalEvent) -> None:
    state.severity = Severity.CRITICAL
    # Create a new LOITERING incident linked to the same track
    new_key = IncidentKey(
        type=IncidentType.LOITERING,
        source_id=event.source_id,
        track_id=event.track_id,
        zone_id=event.zone_id,
    )
    await _open_incident(event, new_key, IncidentType.LOITERING, Severity.CRITICAL)

    # Also upgrade original incident to CRITICAL
    with Session(get_engine()) as session:
        inc = session.get(IncidentRow, state.incident_id)
        if inc:
            inc.severity = Severity.CRITICAL.value
            session.add(inc)
            session.commit()

    await bus.publish(
        "incident.escalated",
        {
            "id": state.incident_id,
            "new_severity": Severity.CRITICAL.value,
        },
    )
    logger.info("Incident %d escalated to CRITICAL (loitering)", state.incident_id)


async def _store_event(event: CanonicalEvent) -> None:
    """Persist one EventRow to SQLite."""
    row = EventRow(
        ts=event.ts,
        source_id=event.source_id,
        frame_id=event.frame_id,
        track_id=event.track_id,
        label=event.label,
        confidence=event.confidence,
        bbox_json=json.dumps(list(event.bbox)) if event.bbox else None,
        zone_id=event.zone_id,
        raw_json=json.dumps(event.raw) if event.raw else None,
    )
    with Session(get_engine()) as session:
        session.add(row)
        session.commit()


# ---------------------------------------------------------------------------
# Auto-close background task
# ---------------------------------------------------------------------------

async def auto_close_loop() -> None:
    """Runs every 2 seconds; resolves stale incidents."""
    while True:
        await asyncio.sleep(2)
        try:
            await _auto_close_tick()
        except Exception as exc:
            logger.error("auto_close error: %s", exc, exc_info=True)


async def _auto_close_tick() -> None:
    now_mono = time.monotonic()
    quiet = float(settings.quiet_seconds)
    stale: list[tuple] = [
        ktuple
        for ktuple, state in list(_states.items())
        if state.open and (now_mono - state.last_seen) > quiet
    ]
    for ktuple in stale:
        state = _states.pop(ktuple, None)
        if state is None or not state.open:
            continue
        await _close_incident(state)


async def _close_incident(state: IncidentState) -> None:
    now_utc = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        inc = session.get(IncidentRow, state.incident_id)
        if inc and inc.status == IncidentStatus.OPEN.value:
            inc.status = IncidentStatus.RESOLVED.value
            inc.last_seen = now_utc
            session.add(inc)
            session.commit()

    await bus.publish(
        "incident.closed",
        {
            "id": state.incident_id,
            "resolved_at": now_utc.isoformat(),
        },
    )
    logger.info("Incident %d auto-closed (quiet for %ds)", state.incident_id, settings.quiet_seconds)
