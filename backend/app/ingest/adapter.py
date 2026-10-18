"""
adapter.py — Converts raw PipeGen MQTT/JSON payloads into CanonicalEvent objects.

Field mapping is driven entirely by backend/config/adapter.yaml so that PipeGen's
actual output schema can be adjusted without touching Python code.

Contract:
  - No model inference.
  - No OpenCV / cv2 / torch / ultralytics imports.
  - Must handle both epoch-ms and ISO-8601 timestamps.
  - Must handle both xyxy and xywh bbox formats.
  - Returns a (possibly empty) list of CanonicalEvent for each raw message.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml

from app.config import settings
from app.schemas import CanonicalEvent

logger = logging.getLogger(__name__)


def _load_config() -> dict[str, Any]:
    path = settings.adapter_yaml_path
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


_cfg: dict[str, Any] | None = None


def _get_cfg() -> dict[str, Any]:
    global _cfg
    if _cfg is None:
        _cfg = _load_config()
    return _cfg


def reload_config() -> None:
    """Force-reload adapter.yaml (useful during development)."""
    global _cfg
    _cfg = _load_config()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve(payload: dict[str, Any], dotted_key: str) -> Any:
    """Resolve a dot-separated key path in a nested dict."""
    parts = dotted_key.split(".")
    val = payload
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


def _parse_ts(raw: Any) -> datetime:
    """Parse epoch-ms int/float or ISO-8601 string into UTC datetime."""
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, (int, float)):
        # Could be epoch-seconds or epoch-ms; treat > 1e12 as ms
        epoch_s = raw / 1000.0 if raw > 1e12 else float(raw)
        return datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _normalize_bbox(
    bbox: list[float] | dict[str, Any] | None,
    bbox_format: str,
    frame_size: list[int],
) -> tuple[float, float, float, float] | None:
    """Return normalised (x, y, w, h) in 0..1 range."""
    if not bbox:
        return None

    fw = float(frame_size[0]) if frame_size and frame_size[0] > 0 else 1920.0
    fh = float(frame_size[1]) if frame_size and frame_size[1] > 0 else 1080.0

    if isinstance(bbox, dict):
        x = float(bbox.get("left", bbox.get("x", 0.0)))
        y = float(bbox.get("top", bbox.get("y", 0.0)))
        w = float(bbox.get("width", bbox.get("w", 0.0)))
        h = float(bbox.get("height", bbox.get("h", 0.0)))
        if not (x <= 1.0 and y <= 1.0 and w <= 1.0 and h <= 1.0):
            x = x / fw
            y = y / fh
            w = w / fw
            h = h / fh
        return (
            max(0.0, min(1.0, x)),
            max(0.0, min(1.0, y)),
            max(0.0, min(1.0, w)),
            max(0.0, min(1.0, h)),
        )

    if len(bbox) < 4:
        return None

    if bbox_format == "xyxy":
        x1, y1, x2, y2 = bbox[:4]
        x = x1 / fw
        y = y1 / fh
        w = (x2 - x1) / fw
        h = (y2 - y1) / fh
    else:  # xywh
        x = bbox[0] / fw
        y = bbox[1] / fh
        w = bbox[2] / fw
        h = bbox[3] / fh

    # If already normalised (all values <= 1), skip division
    if all(v <= 1.0 for v in (x, y, w, h)):
        if bbox_format == "xyxy":
            x, y, w, h = bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]

    return (
        max(0.0, min(1.0, x)),
        max(0.0, min(1.0, y)),
        max(0.0, min(1.0, w)),
        max(0.0, min(1.0, h)),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(raw_payload: dict[str, Any]) -> list[CanonicalEvent]:
    """
    Convert one raw PipeGen payload (dict) into a list of CanonicalEvent objects.
    Returns an empty list on any error (errors are logged, never raised).
    """
    cfg = _get_cfg()
    events: list[CanonicalEvent] = []

    try:
        # Top-level fields with fallbacks for standard PipeGen naming
        source_id: str = str(
            _resolve(raw_payload, cfg.get("source_id", "source_id"))
            or raw_payload.get("camera_id")
            or raw_payload.get("source_id")
            or "unknown"
        )
        frame_id_raw = (
            _resolve(raw_payload, cfg.get("frame_id", "frame"))
            if _resolve(raw_payload, cfg.get("frame_id", "frame")) is not None
            else raw_payload.get("frame_num")
        )
        frame_id: int | None = int(frame_id_raw) if frame_id_raw is not None else None
        ts = _parse_ts(
            _resolve(raw_payload, cfg.get("timestamp", "pts_ns"))
            or raw_payload.get("timestamp")
        )

        # Per-object list
        objects_path: str = cfg.get("objects_path", "objects")
        objects: list[dict[str, Any]] = _resolve(raw_payload, objects_path) or []

        if not isinstance(objects, list):
            objects = [objects]

        fields_cfg: dict[str, str] = cfg.get("fields", {})
        bbox_format: str = cfg.get("bbox_format", "xywh")
        frame_w = raw_payload.get("width") or cfg.get("frame_size", [1920, 1080])[0]
        frame_h = raw_payload.get("height") or cfg.get("frame_size", [1920, 1080])[1]
        frame_size: list[int] = [int(frame_w), int(frame_h)]

        # Check PipeGen fields and shapes for zone and PPE annotations
        fields_data: dict[str, Any] = raw_payload.get("fields", {}) if isinstance(raw_payload.get("fields"), dict) else {}
        shapes_data: list[dict[str, Any]] = raw_payload.get("shapes", []) if isinstance(raw_payload.get("shapes"), list) else []

        for obj in objects:
            if not isinstance(obj, dict):
                continue

            track_id_raw = obj.get(fields_cfg.get("track_id", "id")) if obj.get(fields_cfg.get("track_id", "id")) is not None else obj.get("tracker_id")
            track_id: int | None = int(track_id_raw) if track_id_raw is not None else None

            label: str = str(
                obj.get(fields_cfg.get("label", "label"))
                or obj.get("class")
                or "unknown"
            )
            confidence: float = float(
                obj.get(fields_cfg.get("confidence", "confidence"))
                if obj.get(fields_cfg.get("confidence", "confidence")) is not None
                else obj.get("conf", 0.0)
            )
            bbox_raw = obj.get(fields_cfg.get("bbox", "bbox"))
            zone_id: str | None = obj.get(fields_cfg.get("zone_id", "zone_id")) or obj.get("roi")

            # Check if this track is inside the hazard zone according to PipeGen custom process
            if track_id is not None:
                if fields_data.get(f"track_{track_id}_in_zone") == 1:
                    zone_id = "hazard_zone_1"
                for shape in shapes_data:
                    if shape.get("id") == track_id and "IN_ZONE" in str(shape.get("label", "")):
                        zone_id = "hazard_zone_1"

            bbox = _normalize_bbox(bbox_raw, bbox_format, frame_size)

            # Everything else goes into attributes
            known_keys = set(fields_cfg.values()) | {"tracker_id", "id", "class", "label", "conf", "confidence", "bbox", "roi", "zone_id"}
            attributes = {k: v for k, v in obj.items() if k not in known_keys}

            event = CanonicalEvent(
                event_id=str(uuid.uuid4()),
                ts=ts,
                source_id=source_id,
                frame_id=frame_id,
                track_id=track_id,
                label=label,
                confidence=confidence,
                bbox=bbox,
                zone_id=zone_id if zone_id else None,
                attributes=attributes,
                raw=raw_payload,
            )
            events.append(event)

            # Check for PPE violations flagged by PipeGen for this track
            if track_id is not None and label == "person":
                missing_helmet = (fields_data.get(f"track_{track_id}_helmet") == 0)
                missing_vest = (fields_data.get(f"track_{track_id}_vest") == 0)
                for shape in shapes_data:
                    if shape.get("id") == track_id:
                        lbl = str(shape.get("label", ""))
                        if "missing:hard hat" in lbl or "missing:helmet" in lbl:
                            missing_helmet = True
                        if "missing:safety vest" in lbl or "missing:vest" in lbl:
                            missing_vest = True

                if missing_helmet:
                    events.append(
                        CanonicalEvent(
                            event_id=str(uuid.uuid4()),
                            ts=ts,
                            source_id=source_id,
                            frame_id=frame_id,
                            track_id=track_id,
                            label="no_hardhat",
                            confidence=confidence,
                            bbox=bbox,
                            zone_id=zone_id if zone_id else None,
                            attributes={"violation": "missing_helmet", "person_track_id": track_id},
                            raw=raw_payload,
                        )
                    )
                if missing_vest:
                    events.append(
                        CanonicalEvent(
                            event_id=str(uuid.uuid4()),
                            ts=ts,
                            source_id=source_id,
                            frame_id=frame_id,
                            track_id=track_id,
                            label="no_vest",
                            confidence=confidence,
                            bbox=bbox,
                            zone_id=zone_id if zone_id else None,
                            attributes={"violation": "missing_vest", "person_track_id": track_id},
                            raw=raw_payload,
                        )
                    )

    except Exception as exc:
        logger.warning("adapter.normalize error: %s | payload: %.200s", exc, raw_payload)

    return events
