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
    bbox: list[float] | None,
    bbox_format: str,
    frame_size: list[int],
) -> tuple[float, float, float, float] | None:
    """Return normalised (x, y, w, h) in 0..1 range."""
    if not bbox or len(bbox) < 4:
        return None

    fw, fh = float(frame_size[0]), float(frame_size[1])

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

    # If already normalised (all values ≤ 1), skip division
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
        # Top-level fields
        source_id: str = str(
            _resolve(raw_payload, cfg.get("source_id", "camera_id")) or "unknown"
        )
        frame_id_raw = _resolve(raw_payload, cfg.get("frame_id", "frame_num"))
        frame_id: int | None = int(frame_id_raw) if frame_id_raw is not None else None
        ts = _parse_ts(_resolve(raw_payload, cfg.get("timestamp", "timestamp")))

        # Per-object list
        objects_path: str = cfg.get("objects_path", "objects")
        objects: list[dict[str, Any]] = _resolve(raw_payload, objects_path) or []

        if not isinstance(objects, list):
            objects = [objects]

        fields: dict[str, str] = cfg.get("fields", {})
        bbox_format: str = cfg.get("bbox_format", "xyxy")
        frame_size: list[int] = cfg.get("frame_size", [1920, 1080])
        ppe_labels: list[str] = cfg.get("ppe_violation_labels", [])

        for obj in objects:
            if not isinstance(obj, dict):
                continue

            track_id_raw = obj.get(fields.get("track_id", "tracker_id"))
            track_id: int | None = int(track_id_raw) if track_id_raw is not None else None

            label: str = str(obj.get(fields.get("label", "class"), "unknown"))
            confidence: float = float(obj.get(fields.get("confidence", "conf"), 0.0))
            bbox_raw: list[float] | None = obj.get(fields.get("bbox", "bbox"))
            zone_id: str | None = obj.get(fields.get("zone_id", "roi"))

            bbox = _normalize_bbox(bbox_raw, bbox_format, frame_size)

            # Everything else goes into attributes
            known_keys = set(fields.values()) | {"tracker_id", "class", "conf", "bbox", "roi"}
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

    except Exception as exc:
        logger.warning("adapter.normalize error: %s | payload: %.200s", exc, raw_payload)

    return events
