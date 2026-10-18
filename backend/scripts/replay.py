"""
scripts/replay.py — DEV ONLY: Re-publishes a captured PipeGen output file to MQTT.

Usage:
    python scripts/replay.py <captured_file.json> [--speed 1.0]

⚠️  NEVER use replay for the final demo or evidence.
    This tool exists only to allow UI/backend development without the GPU running.
    Label all dashboard screenshots taken with replay as "REPLAY — not live".

The script reads a JSON or JSONL file, publishes each object to the configured
MQTT broker on the configured topic at the original timing (or scaled by --speed).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure we can import from the parent backend/app directory
sys.path.insert(0, str(Path(__file__).parent.parent))


async def replay(file_path: Path, speed: float = 1.0) -> None:
    try:
        import aiomqtt
    except ImportError:
        print("aiomqtt not installed. Run: pip install aiomqtt")
        sys.exit(1)

    from app.config import settings

    lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    records: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, list):
                records.extend(obj)
            elif isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            pass

    if not records:
        print("No JSON records found in", file_path)
        sys.exit(1)

    topic = settings.mqtt_topic.rstrip("#").rstrip("/")
    if not topic:
        topic = "pipegen/detections"

    print(f"[REPLAY] {len(records)} records → {settings.mqtt_host}:{settings.mqtt_port} / {topic}")
    print("[REPLAY] ⚠️  REPLAY MODE — not live PipeGen output. Do not use as evidence.")

    async with aiomqtt.Client(hostname=settings.mqtt_host, port=settings.mqtt_port) as client:
        for i, record in enumerate(records):
            # Tag as replay so the backend marks data_origin='replay'
            record["_data_origin"] = "replay"
            payload = json.dumps(record).encode()
            await client.publish(topic, payload=payload)
            print(f"  [{i+1}/{len(records)}] published frame {record.get('frame_num', '?')} (REPLAY)")
            delay = 1.0 / (30.0 * speed)  # assume 30 fps source
            await asyncio.sleep(delay)

    print("[REPLAY] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DEV ONLY: replay a captured PipeGen output file to MQTT."
    )
    parser.add_argument("file", type=Path, help="Path to JSON or JSONL capture file")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    asyncio.run(replay(args.file, speed=args.speed))


if __name__ == "__main__":
    main()
