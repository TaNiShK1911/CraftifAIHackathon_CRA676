"""
tests/test_adapter.py — Unit tests for the adapter layer.
Uses the captured real sample in tests/fixtures/sample_payload.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingest.adapter import normalize
from app.schemas import CanonicalEvent


FIXTURE = Path(__file__).parent / "fixtures" / "sample_payload.json"


def _load_fixture() -> dict:
    with open(FIXTURE) as fh:
        return json.load(fh)


def test_adapter_returns_list():
    payload = _load_fixture()
    events = normalize(payload)
    assert isinstance(events, list)
    assert len(events) >= 1


def test_adapter_canonical_shape():
    payload = _load_fixture()
    events = normalize(payload)
    for ev in events:
        assert isinstance(ev, CanonicalEvent)
        assert ev.source_id
        assert ev.label
        assert 0.0 <= ev.confidence <= 1.0


def test_adapter_zone_intrusion_event():
    payload = _load_fixture()
    events = normalize(payload)
    zone_events = [e for e in events if e.zone_id is not None]
    assert len(zone_events) >= 1
    ev = zone_events[0]
    assert ev.label == "person"
    assert ev.zone_id == "hazard_zone_1"


def test_adapter_ppe_violation_event():
    payload = _load_fixture()
    events = normalize(payload)
    ppe_events = [e for e in events if "hardhat" in ev.label or "vest" in ev.label for ev in [e]]
    assert any("hardhat" in e.label or "vest" in e.label for e in events)


def test_adapter_bbox_normalised():
    payload = _load_fixture()
    events = normalize(payload)
    for ev in events:
        if ev.bbox:
            x, y, w, h = ev.bbox
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0
            assert 0.0 <= w <= 1.0
            assert 0.0 <= h <= 1.0


def test_adapter_survives_empty_payload():
    events = normalize({})
    assert events == []


def test_adapter_survives_malformed_objects():
    payload = {"camera_id": "cam0", "objects": "not_a_list"}
    events = normalize(payload)
    # Should not raise, may return empty
    assert isinstance(events, list)


def test_adapter_survives_missing_fields():
    payload = {"camera_id": "cam0", "frame_num": 1, "objects": [{"class": "person"}]}
    events = normalize(payload)
    assert isinstance(events, list)
    if events:
        assert events[0].label == "person"
