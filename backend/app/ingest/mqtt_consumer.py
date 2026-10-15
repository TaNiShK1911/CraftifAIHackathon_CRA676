"""
mqtt_consumer.py — Async MQTT subscriber that reads from the PipeGen broker topic.

Features:
  - Subscribes to the configured topic filter (default pipegen/#).
  - Auto-reconnects with exponential back-off (1s → 30s).
  - Each message is parsed as JSON (single object or array of objects).
  - Malformed payloads are logged and counted; they never crash the loop.
  - Exposes health counters accessible via /api/health.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable, Awaitable, Any

import aiomqtt

from app.config import settings

logger = logging.getLogger(__name__)

# Health counters (read by /api/health)
state = {
    "connected": False,
    "last_message_ts": None,   # monotonic time of last good message
    "dropped_messages": 0,
}

_BACKOFF_START = 1.0
_BACKOFF_MAX = 30.0


async def run(
    on_payload: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Runs forever. Call from a lifespan background task.
    on_payload is called with each decoded JSON dict (one frame worth of detections).
    """
    backoff = _BACKOFF_START
    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
            ) as client:
                state["connected"] = True
                backoff = _BACKOFF_START
                logger.info(
                    "MQTT connected to %s:%s, subscribing to %s",
                    settings.mqtt_host,
                    settings.mqtt_port,
                    settings.mqtt_topic,
                )
                await client.subscribe(settings.mqtt_topic)
                async for message in client.messages:
                    raw_bytes: bytes = message.payload  # type: ignore[assignment]
                    await _handle_raw(raw_bytes, on_payload)

        except aiomqtt.MqttError as exc:
            state["connected"] = False
            logger.warning("MQTT disconnected (%s), reconnecting in %.0fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

        except Exception as exc:
            state["connected"] = False
            logger.error("MQTT unexpected error: %s", exc, exc_info=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)


async def _handle_raw(
    raw_bytes: bytes,
    on_payload: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    try:
        payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        state["dropped_messages"] += 1
        logger.debug("MQTT malformed JSON (dropped): %s", exc)
        return

    state["last_message_ts"] = time.monotonic()

    # PipeGen may send a single dict or an array of dicts
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                await on_payload(item)
            else:
                state["dropped_messages"] += 1
    elif isinstance(payload, dict):
        await on_payload(payload)
    else:
        state["dropped_messages"] += 1
        logger.debug("MQTT unexpected payload type: %s (dropped)", type(payload))
