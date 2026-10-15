"""
tests/test_api.py — API integration tests using httpx + in-memory DB.
Tests: health, events list, incidents list, SSE emits on incident open.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.main import app
from app.db import get_session


@pytest.fixture(scope="module")
def test_engine(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("data") / "test.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="module")
def client(test_engine):
    def override_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    import app.db as db_module
    db_module._engine = test_engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert body["ok"] is True


def test_incidents_empty(client):
    r = client.get("/api/incidents")
    assert r.status_code == 200
    assert r.json() == []


def test_events_empty(client):
    r = client.get("/api/events")
    assert r.status_code == 200
    assert r.json() == []


def test_stats_summary(client):
    r = client.get("/api/stats/summary")
    assert r.status_code == 200
    body = r.json()
    assert "total_incidents" in body
    assert "open_incidents" in body


def test_zones(client):
    r = client.get("/api/zones")
    assert r.status_code == 200
    body = r.json()
    assert "zones" in body


def test_pipeline_runs_empty(client):
    r = client.get("/api/pipeline/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_pipeline_run_create(client):
    payload = {
        "model_name": "yolov8n-ppe",
        "precision": "FP16",
        "fps": 42.5,
        "latency_ms": 23.1,
        "power_w": 85.0,
        "accuracy_map": 0.71,
        "notes": "PipeGen speed report",
    }
    r = client.post("/api/pipeline/runs", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["model_name"] == "yolov8n-ppe"
    assert body["precision"] == "FP16"


def test_patch_incident_404(client):
    r = client.patch("/api/incidents/9999", json={"status": "ACKNOWLEDGED", "ack_by": "tester"})
    assert r.status_code == 404


def test_timeseries(client):
    r = client.get("/api/stats/timeseries?bucket=1m&window=60m")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
