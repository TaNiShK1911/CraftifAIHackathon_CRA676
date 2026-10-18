"""
scripts/import_speed_report.py — Parses a captured PipeGen speed report
and inserts rows into pipeline_runs with data_origin='live'.

Usage:
    python scripts/import_speed_report.py captured/speed_report.csv

Supported formats:
  - CSV with columns: precision, fps, latency_ms, power_w, accuracy_map
  - JSON with a list of objects or a benchmarks dict keyed by precision

IMPORTANT: This script FAILS LOUDLY if a required field is missing.
           It NEVER fills default values for benchmark numbers.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session
from app.db import init_db, get_engine
from app.models import PipelineRunRow

REQUIRED_FIELDS = {"precision", "fps", "latency_ms"}


def parse_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def parse_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Support a benchmarks dict keyed by precision name
        rows = []
        for precision, values in data.items():
            if isinstance(values, dict):
                values["precision"] = precision
                rows.append(values)
        return rows
    raise ValueError(f"Unexpected JSON structure in {path}")


def validate_and_insert(rows: list[dict], source_filename: str, model_name: str) -> None:
    init_db()
    engine = get_engine()

    with Session(engine) as session:
        for row in rows:
            missing = REQUIRED_FIELDS - set(row.keys())
            if missing:
                print(f"ERROR: Missing required fields {missing} in row: {row}")
                print("This script never fills defaults. Fix the source file.")
                sys.exit(1)

            pr = PipelineRunRow(
                model_name=model_name,
                precision=str(row["precision"]).upper(),
                engine_path=row.get("engine_path"),
                fps=float(row["fps"]),
                latency_ms=float(row["latency_ms"]),
                power_w=float(row["power_w"]) if row.get("power_w") else None,
                accuracy_map=float(row["accuracy_map"]) if row.get("accuracy_map") else None,
                notes=f"Imported from {source_filename}",
                data_origin="live",
            )
            session.add(pr)
            print(f"  → {pr.precision}: {pr.fps} FPS, {pr.latency_ms} ms")

        session.commit()
    print(f"Imported {len(rows)} pipeline runs from {source_filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Import a real PipeGen speed report into the pipeline_runs table."
    )
    parser.add_argument("file", type=Path, help="Path to speed report (CSV or JSON)")
    parser.add_argument(
        "--model-name", type=str, default="unknown",
        help="Model name to record (e.g., 'yolov8n-person-ppe')"
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    suffix = args.file.suffix.lower()
    if suffix == ".csv":
        rows = parse_csv(args.file)
    elif suffix == ".json":
        rows = parse_json(args.file)
    else:
        print(f"Unsupported file format: {suffix}. Use .csv or .json")
        sys.exit(1)

    if not rows:
        print("No rows found in the file.")
        sys.exit(1)

    validate_and_insert(rows, args.file.name, args.model_name)


if __name__ == "__main__":
    main()
