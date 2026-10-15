"""
json_tailer.py — Watches PIPEGEN_OUTPUT_DIR with watchfiles for new or appended
JSON / JSONL files, reads only the new bytes (tracks per-file byte offsets so
restarts do not re-ingest), and passes each decoded object through the same
adapter path as the MQTT consumer.

Either MQTT or the tailer may be the primary source; both can run simultaneously.
Deduplication happens in the rules engine on (source_id, frame_id, track_id, label).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Callable, Awaitable, Any

from watchfiles import awatch, Change

from app.config import settings

logger = logging.getLogger(__name__)

# Per-file read offsets so we tail rather than re-read
_offsets: dict[str, int] = {}


async def run(
    on_payload: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Runs forever. Call from a lifespan background task.
    Watches PIPEGEN_OUTPUT_DIR and feeds new JSON/JSONL content to on_payload.
    """
    output_dir = Path(settings.pipegen_output_dir)
    if not output_dir.exists():
        logger.warning(
            "PIPEGEN_OUTPUT_DIR %s does not exist — tailer waiting for it to appear",
            output_dir,
        )
        while not output_dir.exists():
            await asyncio.sleep(5)

    logger.info("JSON tailer watching %s", output_dir)

    try:
        async for changes in awatch(str(output_dir), recursive=True):
            for change_type, path_str in changes:
                path = Path(path_str)
                if path.suffix.lower() not in {".json", ".jsonl"}:
                    continue
                if change_type in (Change.added, Change.modified):
                    await _tail_file(path, on_payload)
    except Exception as exc:
        logger.error("JSON tailer error: %s", exc, exc_info=True)


async def _tail_file(
    path: Path,
    on_payload: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Read only the new bytes of a file since the last read."""
    key = str(path)
    offset = _offsets.get(key, 0)

    try:
        size = path.stat().st_size
    except OSError:
        return

    if size <= offset:
        # File was truncated or no new data
        if size < offset:
            _offsets[key] = 0
            offset = 0
        else:
            return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            new_content = fh.read(size - offset)
            _offsets[key] = fh.tell()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return

    for line in new_content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            # Try treating the whole new_content as one JSON object
            try:
                payload = json.loads(new_content)
                await _dispatch(payload, on_payload)
                break
            except json.JSONDecodeError:
                logger.debug("Skipping unparseable line in %s", path)
                continue

        await _dispatch(payload, on_payload)


async def _dispatch(
    payload: Any,
    on_payload: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                await on_payload(item)
    elif isinstance(payload, dict):
        await on_payload(payload)
