"""
tests/test_provenance.py — Tests for data origin tracking, filtering, and honest reporting.
Verifies that:
- Events and Incidents store and filter by data_origin (live, replay, seed)
- /api/health reports accurate origin counts and contains no fabricated FPS
- /api/incidents and /api/events properly filter when data_origin query param is given
- import_speed_report requires mandatory fields and refuses missing benchmark data
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import get_session
from app.main import app
from app.models import EventRow, IncidentRow, PipelineRunRow


@pytest.fixture(scope="module")
def prov_engine(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("prov_data") / "prov_test.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="module")
def prov_client(prov_engine):
    def override_session():
        with Session(prov_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    import app.db as db_module
    db_module._engine = prov_engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


def test_provenance_incidents_filtering(prov_client, prov_engine):
    # Seed 1 live incident, 1 replay incident, 1 seed incident
    now = datetime.now(timezone.utc)
    with Session(prov_engine) as session:
        inc_live = IncidentRow(
            type="ZONE_INTRUSION",
            severity="HIGH",
            status="OPEN",
            source_id="cam0",
            track_id=1,
            zone_id="danger_zone",
            first_seen=now,
            last_seen=now,
            event_count=5,
            max_confidence=0.92,
            data_origin="live",
        )
        inc_replay = IncidentRow(
            type="PPE_VIOLATION",
            severity="MEDIUM",
            status="OPEN",
            source_id="cam0",
            track_id=2,
            zone_id="hazard_zone",
            first_seen=now,
            last_seen=now,
            event_count=3,
            max_confidence=0.88,
            data_origin="replay",
        )
        inc_seed = IncidentRow(
            type="LOITERING",
            severity="CRITICAL",
            status="OPEN",
            source_id="cam0",
            track_id=3,
            zone_id="restricted_zone",
            first_seen=now,
            last_seen=now,
            event_count=10,
            max_confidence=0.95,
            data_origin="seed",
        )
        session.add(inc_live)
        session.add(inc_replay)
        session.add(inc_seed)
        session.commit()

    # Query all incidents
    r_all = prov_client.get("/api/incidents")
    assert r_all.status_code == 200
    all_data = r_all.json()
    assert len(all_data) >= 3

    # Filter live only
    r_live = prov_client.get("/api/incidents?data_origin=live")
    assert r_live.status_code == 200
    live_data = r_live.json()
    assert all(i["data_origin"] == "live" for i in live_data)
    assert any(i["track_id"] == 1 for i in live_data)
    assert not any(i["track_id"] in (2, 3) for i in live_data)

    # Filter replay only
    r_replay = prov_client.get("/api/incidents?data_origin=replay")
    assert r_replay.status_code == 200
    replay_data = r_replay.json()
    assert all(i["data_origin"] == "replay" for i in replay_data)
    assert any(i["track_id"] == 2 for i in replay_data)

    # Filter seed only
    r_seed = prov_client.get("/api/incidents?data_origin=seed")
    assert r_seed.status_code == 200
    seed_data = r_seed.json()
    assert all(i["data_origin"] == "seed" for i in seed_data)
    assert any(i["track_id"] == 3 for i in seed_data)


def test_provenance_events_filtering(prov_client, prov_engine):
    now = datetime.now(timezone.utc)
    with Session(prov_engine) as session:
        ev_live = EventRow(
            ts=now,
            source_id="cam0",
            track_id=101,
            label="person",
            confidence=0.91,
            zone_id="zone1",
            data_origin="live",
        )
        ev_replay = EventRow(
            ts=now,
            source_id="cam0",
            track_id=102,
            label="no_helmet",
            confidence=0.85,
            zone_id="zone1",
            data_origin="replay",
        )
        session.add(ev_live)
        session.add(ev_replay)
        session.commit()

    # Query live events
    r_live = prov_client.get("/api/events?data_origin=live")
    assert r_live.status_code == 200
    events_live = r_live.json()
    assert all(e["data_origin"] == "live" for e in events_live)
    assert any(e["track_id"] == 101 for e in events_live)
    assert not any(e["track_id"] == 102 for e in events_live)

    # Query replay events
    r_replay = prov_client.get("/api/events?data_origin=replay")
    assert r_replay.status_code == 200
    events_replay = r_replay.json()
    assert all(e["data_origin"] == "replay" for e in events_replay)
    assert any(e["track_id"] == 102 for e in events_replay)


def test_health_honesty(prov_client):
    r = prov_client.get("/api/health")
    assert r.status_code == 200
    data = r.json()

    # Must NOT have fabricated fps
    assert "fps" not in data or data["fps"] is None
    # Must report origin breakdowns
    assert "events_by_origin" in data
    assert "incidents_by_origin" in data
    assert data["incidents_by_origin"].get("live", 0) >= 1
    assert data["incidents_by_origin"].get("replay", 0) >= 1
    assert data["incidents_by_origin"].get("seed", 0) >= 1


def test_import_speed_report_validation(tmp_path):
    from scripts.import_speed_report import parse_csv, validate_and_insert

    # Valid CSV
    valid_csv = tmp_path / "valid_speed_report.csv"
    with open(valid_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["precision", "fps", "latency_ms", "power_w", "accuracy_map"])
        writer.writeheader()
        writer.writerow({
            "precision": "FP16",
            "fps": "88.4",
            "latency_ms": "11.3",
            "power_w": "65.0",
            "accuracy_map": "0.785",
        })

    rows = parse_csv(valid_csv)
    assert len(rows) == 1
    assert rows[0]["precision"] == "FP16"
    assert rows[0]["fps"] == "88.4"

    # Invalid CSV missing required field
    invalid_csv = tmp_path / "invalid_speed_report.csv"
    with open(invalid_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["precision", "power_w"])
        writer.writeheader()
        writer.writerow({"precision": "INT8", "power_w": "45.0"})

    bad_rows = parse_csv(invalid_csv)
    with pytest.raises(ValueError, match="missing required fields"):
        validate_and_insert(bad_rows, source_filename="invalid.csv", model_name="test-model")

    # Valid CSV with empty power/accuracy and engine_path derivation
    multi_csv = tmp_path / "multi_speed_report.csv"
    with open(multi_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["precision", "fps", "latency_ms", "power_w", "accuracy_map", "engine_path"])
        writer.writeheader()
        writer.writerow({
            "precision": "FP32",
            "fps": "30.75",
            "latency_ms": "32.525",
            "power_w": "32.44",
            "accuracy_map": "",
            "engine_path": "model_stage/yolo11s.fp32.plan",
        })
        writer.writerow({
            "precision": "FP32",
            "fps": "66.2",
            "latency_ms": "15.105",
            "power_w": "",
            "accuracy_map": "",
            "engine_path": "model_stage/6-best/best.fp32.plan",
        })

    multi_rows = parse_csv(multi_csv)
    validate_and_insert(multi_rows, source_filename="multi_speed_report.csv")

    from app.db import get_engine
    from app.models import PipelineRunRow
    from sqlmodel import Session, select

    with Session(get_engine()) as session:
        imported = session.exec(
            select(PipelineRunRow).where(PipelineRunRow.notes == "Imported from multi_speed_report.csv")
        ).all()
        assert len(imported) == 2
        models = {r.model_name for r in imported}
        assert "yolo11s" in models
        assert "best" in models
        for r in imported:
            assert r.data_origin == "live"
            assert r.accuracy_map is None
        yolo_run = next(r for r in imported if r.model_name == "yolo11s")
        assert yolo_run.power_w == 32.44
        best_run = next(r for r in imported if r.model_name == "best")
        assert best_run.power_w is None

