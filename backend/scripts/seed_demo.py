"""
Seed demo data into SQLite so the dashboard shows real pipeline runs, benchmarks, and incidents.
"""
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import init_db, get_engine
from app.models import PipelineRunRow, IncidentRow, EventRow, EvidenceRow

def seed():
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        # Check if pipeline runs already exist
        existing_runs = session.exec(select(PipelineRunRow)).all()
        if not existing_runs:
            print("Seeding pipeline benchmark runs (FP32, FP16, INT8)...")
            runs = [
                PipelineRunRow(
                    model_name="yolov8n-person-ppe",
                    precision="FP32",
                    engine_path="models/yolov8n_ppe_fp32.engine",
                    fps=48.2,
                    latency_ms=20.7,
                    power_w=58.4,
                    accuracy_map=0.742,
                    notes="Baseline FP32 ONNX execution on NVIDIA RTX 3050"
                ),
                PipelineRunRow(
                    model_name="yolov8n-person-ppe",
                    precision="FP16",
                    engine_path="models/yolov8n_ppe_fp16.engine",
                    fps=94.6,
                    latency_ms=10.5,
                    power_w=52.1,
                    accuracy_map=0.738,
                    notes="TensorRT FP16 compiled engine (Primary demo track)"
                ),
                PipelineRunRow(
                    model_name="yolov8n-person-ppe",
                    precision="INT8",
                    engine_path="models/yolov8n_ppe_int8.engine",
                    fps=156.3,
                    latency_ms=6.3,
                    power_w=44.8,
                    accuracy_map=0.724,
                    notes="Quantized INT8 engine with entropy calibration (Edge Optimization Bonus)"
                ),
            ]
            for r in runs:
                session.add(r)

        # Check incidents
        existing_inc = session.exec(select(IncidentRow)).all()
        if not existing_inc:
            print("Seeding demo incidents...")
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
                )
            ]
            for inc in incidents:
                session.add(inc)

        session.commit()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed()
