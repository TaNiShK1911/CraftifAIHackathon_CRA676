"""
Seed demo data into SQLite so the dashboard has something to display
during development. All rows are marked data_origin='seed'.

Usage:
    python scripts/seed_demo.py --allow-synthetic

Without --allow-synthetic the script refuses to run, to prevent
accidental insertion of synthetic data into a live demo database.

This script DOES NOT insert pipeline benchmark runs. Benchmark data
must come from a real PipeGen speed report via import_speed_report.py.
"""
from datetime import datetime, timezone, timedelta
import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import init_db, get_engine
from app.models import IncidentRow, EventRow


def seed():
    parser = argparse.ArgumentParser(
        description="Seed synthetic demo incidents into the database (marked as seed)."
    )
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        required=True,
        help="Required flag to confirm you want to insert synthetic data.",
    )
    args = parser.parse_args()

    init_db()
    engine = get_engine()
    with Session(engine) as session:
        # Check incidents
        existing_inc = session.exec(
            select(IncidentRow).where(IncidentRow.data_origin == "seed")
        ).all()
        if existing_inc:
            print(f"Already have {len(existing_inc)} seeded incidents — skipping.")
        else:
            print("Seeding demo incidents (data_origin='seed')...")
            now = datetime.now(timezone.utc)
            incidents = [
                IncidentRow(
                    type="ZONE_INTRUSION",
                    severity="HIGH",
                    status="OPEN",
                    source_id="cam0",
                    track_id=14,
                    zone_id="hazard_zone_1",
                    first_seen=now - timedelta(minutes=12),
                    last_seen=now - timedelta(seconds=15),
                    event_count=42,
                    max_confidence=0.94,
                    data_origin="seed",
                ),
                IncidentRow(
                    type="PPE_VIOLATION",
                    severity="MEDIUM",
                    status="OPEN",
                    source_id="cam0",
                    track_id=9,
                    zone_id="walkway_b",
                    first_seen=now - timedelta(minutes=25),
                    last_seen=now - timedelta(minutes=2),
                    event_count=18,
                    max_confidence=0.88,
                    data_origin="seed",
                ),
                IncidentRow(
                    type="LOITERING",
                    severity="CRITICAL",
                    status="OPEN",
                    source_id="cam0",
                    track_id=14,
                    zone_id="hazard_zone_1",
                    first_seen=now - timedelta(minutes=8),
                    last_seen=now - timedelta(seconds=10),
                    event_count=85,
                    max_confidence=0.96,
                    data_origin="seed",
                ),
                IncidentRow(
                    type="PPE_VIOLATION",
                    severity="MEDIUM",
                    status="RESOLVED",
                    source_id="cam0",
                    track_id=3,
                    zone_id="assembly_zone",
                    first_seen=now - timedelta(hours=2),
                    last_seen=now - timedelta(hours=1, minutes=45),
                    event_count=12,
                    max_confidence=0.82,
                    ack_by="Site Operator",
                    ack_at=now - timedelta(hours=1, minutes=50),
                    data_origin="seed",
                ),
            ]
            for inc in incidents:
                session.add(inc)

        session.commit()
    print("Database seeded successfully! (all rows marked data_origin='seed')")


if __name__ == "__main__":
    seed()
