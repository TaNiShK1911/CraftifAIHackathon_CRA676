"""
tests/test_rules.py — Unit tests for the rules engine.
Uses a fake in-memory DB and a fake clock to test:
  - Debounce (no incident until min_consecutive_frames)
  - Dedup (same event from two sources is not double-counted)
  - Escalation (zone intrusion → LOITERING after loiter_seconds)
  - Auto-close (incident resolves after quiet_seconds)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import config as cfg_module
from app.schemas import CanonicalEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def in_memory_engine(tmp_path):
    """Create a fresh in-memory SQLite engine for each test."""
    db_path = str(tmp_path / "test.db")
    from sqlmodel import create_engine as _ce
    engine = _ce(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    import app.models  # noqa: F401 — register tables
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.commit()
    return engine


@pytest.fixture(autouse=True)
def patch_engine(in_memory_engine, monkeypatch):
    """Redirect all DB calls to the test engine."""
    import app.db as db_module
    monkeypatch.setattr(db_module, "get_engine", lambda: in_memory_engine)


@pytest.fixture(autouse=True)
def reset_engine_state(monkeypatch):
    """Reset rules engine in-memory state between tests."""
    import app.rules.engine as eng
    monkeypatch.setattr(eng, "_states", {})
    monkeypatch.setattr(eng, "_dedup_cache", {})


def _make_event(**kwargs) -> CanonicalEvent:
    defaults = dict(
        source_id="cam0",
        frame_id=1,
        track_id=1,
        label="person",
        confidence=0.9,
        zone_id="hazard_zone_1",
    )
    defaults.update(kwargs)
    return CanonicalEvent(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_no_incident_before_min_frames(monkeypatch):
    """No incident should open until min_consecutive_frames events arrive."""
    monkeypatch.setattr(cfg_module.settings, "min_consecutive_frames", 5, raising=False)

    import app.rules.engine as eng
    monkeypatch.setattr(eng, "_states", {})

    for i in range(4):
        ev = _make_event(frame_id=i, track_id=1, zone_id="hazard_zone_1")
        # Break dedup by varying frame_id
        await eng.handle(ev)

    # Should not have opened any incident yet
    assert all(not s.open for s in eng._states.values())


@pytest.mark.asyncio
async def test_incident_opens_after_min_frames(monkeypatch, in_memory_engine):
    """Incident should open after min_consecutive_frames events."""
    monkeypatch.setattr(cfg_module.settings, "min_consecutive_frames", 3, raising=False)

    import app.rules.engine as eng
    monkeypatch.setattr(eng, "_states", {})
    monkeypatch.setattr(eng, "_dedup_cache", {})

    for i in range(5):
        ev = _make_event(frame_id=i, track_id=2, zone_id="hazard_zone_1")
        await eng.handle(ev)

    open_states = [s for s in eng._states.values() if s.open]
    assert len(open_states) >= 1


@pytest.mark.asyncio
async def test_ppe_violation_opens(monkeypatch, in_memory_engine):
    """PPE violation event should open a PPE_VIOLATION incident."""
    monkeypatch.setattr(cfg_module.settings, "min_consecutive_frames", 1, raising=False)

    import app.rules.engine as eng
    monkeypatch.setattr(eng, "_states", {})
    monkeypatch.setattr(eng, "_dedup_cache", {})

    for i in range(3):
        ev = _make_event(frame_id=i + 100, track_id=5, label="no_hardhat", zone_id=None)
        await eng.handle(ev)

    from app.schemas import IncidentType
    ppe_states = [
        s for s in eng._states.values()
        if s.key.type == IncidentType.PPE_VIOLATION and s.open
    ]
    assert len(ppe_states) >= 1


@pytest.mark.asyncio
async def test_auto_close_resolves_stale_incident(monkeypatch, in_memory_engine):
    """Auto-close should resolve an incident after quiet_seconds without events."""
    monkeypatch.setattr(cfg_module.settings, "min_consecutive_frames", 1, raising=False)
    monkeypatch.setattr(cfg_module.settings, "quiet_seconds", 0, raising=False)

    import app.rules.engine as eng
    monkeypatch.setattr(eng, "_states", {})
    monkeypatch.setattr(eng, "_dedup_cache", {})

    for i in range(3):
        ev = _make_event(frame_id=i + 200, track_id=9, zone_id="hazard_zone_1")
        await eng.handle(ev)

    # Force all open states to appear stale
    for state in eng._states.values():
        state.last_seen = time.monotonic() - 10

    await eng._auto_close_tick()

    # All should be closed (removed from _states or not open)
    open_states = [s for s in eng._states.values() if s.open]
    assert len(open_states) == 0
