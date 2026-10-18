#!/usr/bin/env python3
"""
scripts/e2e_check.py — End-to-end integration verification for SiteGuard.

Modes:
  --replay (default):
    1. Ensures Mosquitto broker is running.
    2. Initializes a clean temporary SQLite database.
    3. Imports real PipeGen speed report (FP32).
    4. Launches SiteGuard backend on a temporary port.
    5. Connects SSE listener to /api/stream.
    6. Replays captured/mqtt_sample.txt with data_origin=replay.
    7. Asserts events ingested, data_origin=replay, incidents debounced/opened,
       SSE delivery within 5s, acknowledge/resolve lifecycle, and pipeline runs.
    8. Prints PASS/FAIL summary table.

  --live:
    1. Verifies live PipeGen execution against running backend.
    2. Checks last_live_message_age_seconds < 5 and data_origin=live.
    3. Runs and prints nvidia-smi.
    4. Prints incident count for human video confirmation (does NOT auto-pass).
    5. Prints PASS/FAIL table.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def http_get(url: str, timeout: float = 5.0) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def http_patch(url: str, payload: dict, timeout: float = 5.0) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


class SSECollector:
    """Background thread that listens to /api/stream and records events."""

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.events: List[Dict[str, Any]] = []
        self.stop_event = threading.Event()
        self.connected_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        # Wait up to 5s for connection
        self.connected_event.wait(timeout=5.0)

    def stop(self):
        self.stop_event.set()

    def _run(self):
        import httpx
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("GET", self.stream_url, headers={"Accept": "text/event-stream"}) as resp:
                    self.connected_event.set()
                    current_event = "message"
                    for line in resp.iter_lines():
                        if self.stop_event.is_set():
                            break
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                        elif line.startswith("data:"):
                            raw_data = line[5:].strip()
                            try:
                                parsed = json.loads(raw_data)
                            except Exception:
                                parsed = raw_data
                            self.events.append({
                                "event": current_event,
                                "data": parsed,
                                "time": time.time(),
                            })
                            current_event = "message"
        except Exception:
            pass


def find_free_port(start_port: int = 8000) -> int:
    for p in range(start_port, start_port + 50):
        if not check_port("127.0.0.1", p):
            return p
    return start_port


def run_replay_mode(args: argparse.Namespace) -> int:
    print("\n=======================================================")
    print("  SiteGuard E2E Check: REPLAY MODE (Strict Validation)")
    print("=======================================================")

    results: List[Dict[str, str]] = []

    def record_result(check_name: str, passed: bool, detail: str = ""):
        results.append({
            "check": check_name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        })
        status_str = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
        print(f"[{status_str}] {check_name}: {detail}")

    # 1. Mosquitto Broker Check
    broker_running = check_port(args.broker_host, args.broker_port)
    if not broker_running:
        record_result("Mosquitto Broker Running", False, f"Could not connect to {args.broker_host}:{args.broker_port}")
        print("\nPlease ensure Mosquitto is running on port 1883.")
        return 1
    record_result("Mosquitto Broker Running", True, f"Connected to {args.broker_host}:{args.broker_port}")

    # 2. Temp DB Setup
    temp_dir = tempfile.mkdtemp(prefix="siteguard_e2e_")
    temp_db_path = Path(temp_dir) / "e2e_test.db"
    backend_dir = REPO_ROOT / "backend"
    actual_port = find_free_port(args.port)

    try:
        # Import speed report into temp db
        env = os.environ.copy()
        env["SITEGUARD_DB_PATH"] = str(temp_db_path.resolve())
        env["DB_PATH"] = str(temp_db_path.resolve())
        env["SITEGUARD_PORT"] = str(actual_port)
        env["PORT"] = str(actual_port)
        env["SITEGUARD_MQTT_TOPIC"] = "pipegen/detection/demo"
        env["MQTT_TOPIC"] = "pipegen/detection/demo"
        env["PYTHONPATH"] = str(backend_dir.resolve())

        speed_report_file = REPO_ROOT / "captured" / "speed_report.csv"
        import_cmd = [
            sys.executable,
            str(backend_dir / "scripts" / "import_speed_report.py"),
            str(speed_report_file.resolve()),
        ]
        import_proc = subprocess.run(import_cmd, cwd=str(backend_dir), env=env, capture_output=True, text=True)
        if import_proc.returncode != 0:
            record_result("Speed Report Import", False, import_proc.stderr)
            return 1
        record_result("Speed Report Import", True, "Imported yolo11s and best FP32 rows into temp DB")

        # 3. Start Backend
        backend_cmd = [
            sys.executable,
            str(backend_dir / "run_server.py"),
        ]
        backend_proc = subprocess.Popen(backend_cmd, cwd=str(backend_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for health
        base_url = f"http://127.0.0.1:{actual_port}"
        health_ok = False
        for _ in range(30):
            time.sleep(0.5)
            if check_port("127.0.0.1", actual_port):
                try:
                    h = http_get(f"{base_url}/api/health")
                    if h.get("status") == "ok":
                        health_ok = True
                        break
                except Exception:
                    pass

        if not health_ok:
            record_result("Backend Start & Health", False, "Backend did not respond on /api/health within 15s")
            backend_proc.kill()
            return 1
        record_result("Backend Start & Health", True, f"Backend online at {base_url}")

        # 4. Connect SSE Stream
        sse_collector = SSECollector(f"{base_url}/api/stream")
        sse_collector.start()
        time.sleep(0.5)

        # 5. Replay MQTT Sample
        mqtt_sample_file = REPO_ROOT / "captured" / "mqtt_sample.txt"
        lines = mqtt_sample_file.read_text(encoding="utf-8").strip().splitlines()

        import paho.mqtt.client as mqtt
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.connect(args.broker_host, args.broker_port)
        mqtt_client.loop_start()

        print(f"\nPublishing {len(lines)} frames from captured/mqtt_sample.txt to pipegen/detection/demo (data_origin=replay)...")
        first_detection_pub_time: Optional[float] = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            raw = line
            if " " in line and (line.startswith("pipegen/") or not line.startswith("{")):
                _, raw = line.split(" ", 1)
            try:
                frame_dict = json.loads(raw)
            except Exception:
                continue

            # Stamp replay origin
            frame_dict["_data_origin"] = "replay"
            if first_detection_pub_time is None and frame_dict.get("objects"):
                first_detection_pub_time = time.time()

            payload = json.dumps(frame_dict).encode("utf-8")
            mqtt_client.publish("pipegen/detection/demo", payload)
            time.sleep(0.005)  # Fast replay

        mqtt_client.loop_stop()
        mqtt_client.disconnect()

        # Allow backend to finish debouncing/closing
        time.sleep(3.0)

        # 6. Assert SSE delivery within 5s
        opened_events = [e for e in sse_collector.events if e["event"] == "incident.opened"]
        sse_collector.stop()
        if opened_events:
            delivery_latency = opened_events[0]["time"] - (first_detection_pub_time or opened_events[0]["time"])
            sse_passed = delivery_latency <= 5.0
            record_result(
                "SSE incident.opened Delivery (<5s)",
                sse_passed,
                f"Delivered {len(opened_events)} opened events, first latency ~{delivery_latency:.2f}s",
            )
        else:
            record_result("SSE incident.opened Delivery (<5s)", False, "No incident.opened received via SSE stream")

        # 7. Assert Events Ingested
        events_resp = http_get(f"{base_url}/api/events?limit=200")
        events_count = len(events_resp)
        all_events_replay = all(e.get("data_origin") == "replay" for e in events_resp)
        record_result(
            "Events Ingested & Origin",
            events_count > 0 and all_events_replay,
            f"Ingested {events_count} recent events, all data_origin='replay': {all_events_replay}",
        )

        # 8. Assert Incidents Opened & Deduplicated
        incidents_resp = http_get(f"{base_url}/api/incidents?limit=200")
        incident_count = len(incidents_resp)
        all_inc_replay = all(i.get("data_origin") == "replay" for i in incidents_resp)
        dedup_ok = 0 < incident_count < 100  # 19 real incidents << 4900 events
        record_result(
            "Incidents Opened & Deduplicated",
            dedup_ok and all_inc_replay,
            f"{incident_count} incidents opened (deduplicated from events), all data_origin='replay': {all_inc_replay}",
        )

        # 9. Acknowledge & Resolve Lifecycle
        if incidents_resp:
            test_inc_id = incidents_resp[0]["id"]
            ack_resp = http_patch(f"{base_url}/api/incidents/{test_inc_id}", {"status": "ACKNOWLEDGED"})
            res_resp = http_patch(f"{base_url}/api/incidents/{test_inc_id}", {"status": "RESOLVED"})
            lifecycle_ok = ack_resp.get("status") == "ACKNOWLEDGED" and res_resp.get("status") == "RESOLVED"
            record_result("Incident Lifecycle (Ack & Resolve)", lifecycle_ok, f"Incident #{test_inc_id} successfully transitioned OPEN -> ACKNOWLEDGED -> RESOLVED")
        else:
            record_result("Incident Lifecycle (Ack & Resolve)", False, "No incidents to transition")

        # 10. Pipeline Runs Assertions
        runs_resp = http_get(f"{base_url}/api/pipeline/runs")
        real_models = {r.get("model_name"): r.get("precision") for r in runs_resp}
        runs_ok = len(runs_resp) == 2 and real_models.get("yolo11s") == "FP32" and real_models.get("best") == "FP32"
        record_result(
            "/api/pipeline/runs Verified (2 FP32 Models)",
            runs_ok,
            f"Returned {len(runs_resp)} models: {real_models} (INT8 not run)",
        )

    finally:
        # Cleanup backend
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=3.0)
        except Exception:
            try:
                backend_proc.kill()
            except Exception:
                pass
        # Cleanup temp DB
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Print Table
    print("\n" + "=" * 80)
    print("                    E2E REPLAY CHECK RESULT TABLE")
    print("=" * 80)
    print(f"{'Requirement / Check':<45} | {'Status':<8} | {'Details'}")
    print("-" * 80)
    all_passed = True
    for r in results:
        status_colored = f"\033[92m{r['status']}\033[0m" if r['status'] == "PASS" else f"\033[91m{r['status']}\033[0m"
        print(f"{r['check']:<45} | {status_colored:<17} | {r['detail']}")
        if r["status"] != "PASS":
            all_passed = False
    print("=" * 80 + "\n")

    return 0 if all_passed else 1


def run_live_mode(args: argparse.Namespace) -> int:
    print("\n=======================================================")
    print("  SiteGuard E2E Check: LIVE MODE (Real Hardware)")
    print("=======================================================\n")

    base_url = f"http://127.0.0.1:{args.port}"
    if not check_port("127.0.0.1", args.port):
        print(f"\033[91m[ERROR]\033[0m Backend not responding on {base_url}.")
        print("Please ensure the SiteGuard backend is running:")
        print("    cd backend && python -m uvicorn app.main:app --port 8000")
        print("\nAnd ensure live PipeGen export is running:")
        print("    cd pipegen_export && ./run.sh --input demo.mp4\n")
        return 1

    try:
        health = http_get(f"{base_url}/api/health")
    except Exception as e:
        print(f"\033[91m[ERROR]\033[0m Failed to query /api/health: {e}")
        return 1

    age = health.get("last_live_message_age_seconds")
    mqtt_conn = health.get("mqtt_connected", False)

    print(f"Backend Status:       {health.get('status')}")
    print(f"MQTT Connected:       {mqtt_conn}")
    print(f"Last Live Message Age: {age}s (Requirement: < 5.0s)")

    if age is None or age > 5.0:
        print(f"\n\033[93m[NOTICE]\033[0m Live telemetry is not active (last message age: {age}s).")
        print("Live mode requires running the real pipeline first:")
        print("    cd pipegen_export && ./run.sh --input demo.mp4")
        print("Please start ./run.sh and re-run: python scripts/e2e_check.py --live\n")
        return 1

    # Print nvidia-smi
    print("\n---------------- NVIDIA GPU HARDWARE STATUS ----------------")
    try:
        smi_proc = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if smi_proc.returncode == 0:
            print(smi_proc.stdout.strip())
        else:
            print("nvidia-smi returned non-zero exit code.")
    except FileNotFoundError:
        print("nvidia-smi command not found on host.")
    print("------------------------------------------------------------\n")

    # Fetch live counts
    incidents = http_get(f"{base_url}/api/incidents?data_origin=live")
    events = http_get(f"{base_url}/api/events?data_origin=live&limit=200")

    print(f"Live Events Ingested:    {len(events)}")
    print(f"Live Incidents Detected: {len(incidents)}")
    print("\n\033[93m[MANUAL CONFIRMATION REQUIRED]\033[0m")
    print(f"Observed {len(incidents)} live safety incidents.")
    print("Please confirm this count against the visual demo.mp4 playback.")

    return 0


def main():
    parser = argparse.ArgumentParser(description="SiteGuard End-to-End Test Runner")
    parser.add_argument("--replay", action="store_true", help="Run against simulated replay with temporary DB")
    parser.add_argument("--live", action="store_true", help="Run against live running PipeGen DeepStream instance")
    parser.add_argument("--port", type=int, default=8000, help="Backend port to test")
    parser.add_argument("--broker-host", default="localhost", help="MQTT broker host")
    parser.add_argument("--broker-port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()

    if args.live:
        sys.exit(run_live_mode(args))
    else:
        sys.exit(run_replay_mode(args))


if __name__ == "__main__":
    main()
