"""
tests/test_real_mqtt_regression.py — Regression test feeding real captured PipeGen telemetry
from captured/mqtt_sample.txt through the adapter and rules engine.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, select, delete

from app.db import init_db, get_engine
from app.ingest import adapter
from app.models import IncidentRow, EventRow
from app.rules import engine as rules_engine


@pytest.mark.asyncio
async def test_real_mqtt_regression(capsys):
    init_db()
    engine = get_engine()
    # Reset in-memory states and wipe test tables for a clean test run
    rules_engine._states.clear()
    rules_engine._dedup_cache.clear()
    with Session(engine) as session:
        session.exec(delete(IncidentRow))
        session.exec(delete(EventRow))
        session.commit()

    sample_file = Path(__file__).resolve().parent.parent.parent / "captured" / "mqtt_sample.txt"
    assert sample_file.exists(), f"Missing real capture file: {sample_file}"

    lines = sample_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0

    events_list = []
    for line in lines:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        payload = json.loads(parts[1])
        evs = adapter.normalize(payload)
        for ev in evs:
            ev.data_origin = "live"
            events_list.append(ev)
            await rules_engine.handle(ev)

    engine = get_engine()
    with Session(engine) as session:
        incidents = session.exec(select(IncidentRow)).all()

        total_lines = len(lines)
        total_events = len(events_list)
        total_incidents = len(incidents)

        # Print real computed numbers for audit
        print("\n--- Real PipeGen Telemetry Regression Results ---")
        print(f"Total MQTT Frames Fed: {total_lines}")
        print(f"Total Canonical Events: {total_events}")
        print(f"Total Incidents Opened: {total_incidents}")

        # Assertions from computed numbers
        assert total_lines == 395
        assert total_events == 4901
        assert total_incidents > 0
        assert total_incidents < total_events  # De-duplication and debouncing verified

        incident_types = {inc.type for inc in incidents}
        print(f"Incident Types Detected: {sorted(incident_types)}")
        assert "ZONE_INTRUSION" in incident_types
        assert "PPE_VIOLATION" in incident_types

        # Verify auto-close mechanism
        # Simulate time passing beyond quiet_seconds
        for state in rules_engine._states.values():
            state.last_seen -= 20.0  # past quiet_seconds (8s)

        await rules_engine._auto_close_tick()

        # Re-query incidents from DB
        closed_incidents = session.exec(
            select(IncidentRow).where(IncidentRow.status == "RESOLVED")
        ).all()
        print(f"Total Auto-Closed Incidents: {len(closed_incidents)}")
        assert len(closed_incidents) == total_incidents
        print("--- End of Regression Results ---\n")
