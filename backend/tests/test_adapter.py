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


def test_adapter_handles_real_pipegen_format():
    payload = {
        "frame": 30,
        "source_id": 0,
        "pts_ns": 1280000000,
        "width": 2560,
        "height": 1440,
        "objects": [
            {
                "id": 0,
                "class_id": 0,
                "label": "person",
                "confidence": 0.5682,
                "bbox": {"left": 341.7, "top": 423.6, "width": 91.8, "height": 71.8},
                "tracker_confidence": 1.0,
            }
        ],
        "shapes": [
            {
                "kind": "polygon",
                "points": [[256.0, 432.0], [1280.0, 432.0], [1280.0, 1152.0], [256.0, 1152.0]],
                "label": "hazard_zone",
            },
            {
                "kind": "box",
                "x": 341.7,
                "y": 423.6,
                "w": 91.8,
                "h": 71.8,
                "label": "person IN_ZONE missing:hard hat,safety vest",
                "id": 0,
                "score": 1.0,
            },
        ],
        "fields": {
            "current_people": 1,
            "current_in_zone": 1,
            "track_0_in_zone": 1,
            "track_0_helmet": 0,
            "track_0_vest": 0,
        },
    }
    events = normalize(payload)
    assert len(events) >= 1
    person_ev = next(e for e in events if e.label == "person")
    assert person_ev.zone_id == "hazard_zone_1"
    assert person_ev.track_id == 0
    assert person_ev.bbox is not None
    x, y, w, h = person_ev.bbox
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    # Also verify that missing PPE generated canonical violation events
    labels = {e.label for e in events}
    assert "no_hardhat" in labels
    assert "no_vest" in labels

