# Hackathon Submission — Track A (PipeGen)

## Submission Metadata

- **Track:** Track A — PipeGen (Edge AI Vision Pipeline)
- **Project Name:** SiteGuard — Workplace Safety Sentinel
- **Target Problem:** High-throughput construction site safety monitoring. Turning per-frame edge perception into deduplicated, stateful safety incidents (restricted hazard zone intrusions, PPE violations, and loitering) with an operational incident management control room.
- **Product Used:** CraftifAI PipeGen v0.5.1
- **Platform Email:** `tanishkbhanage@gmail.com`
- **Repository URL:** `https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676`
- **Bonus Claimed:** **None claimed** *(Strict Honesty: Both models were compiled and profiled in FP32; INT8 calibration was not executed during this run, and FP16 was not run. The Edge Optimization bonus requires an INT8 engine compiled on-device, so it is not claimed).*

---

## Pipeline Specification

- **Input:**
  - Source: [`demo.mp4`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/export/pipeline/pipeline.sh)
  - Resolution: 2560 × 1440
  - Frame Count: 395 frames (16 seconds @ 25 FPS)
- **Tasks & Perception:**
  1. Primary Person Detection & Hungarian Tracking
  2. Hazard Zone Polygon Intersection (`[[256, 432], [1280, 432], [1280, 1152], [256, 1152]]`)
  3. Six-class PPE Violation Detection (hard hat, safety vest)
  4. Loitering Escalation (>10 seconds in restricted hazard zone)
- **Models & On-Device Compilation:**
  - Primary Detector: `yolo11s.onnx` (RestrictedAreaMonitoring catalog) &rarr; TensorRT FP32 plan (`yolo11s.fp32.plan`, 49.1 MB, 234 TRT layers)
  - Secondary PPE Detector: `best.onnx` (ppe-kit catalog) &rarr; TensorRT FP32 plan (`best.fp32.plan`, 17.9 MB, 196 TRT layers)
- **Execution Hardware:**
  - GPU: NVIDIA GeForce RTX 3050 Laptop GPU (4 GB GDDR6 VRAM, 60W TGP)
  - OS / Host: WSL2 Ubuntu 24.04 on Windows 11
  - NVIDIA Driver: 591.74 | CUDA 13.1 / 12.6
  - TensorRT: 10.3.0
  - Container: `craftifaidocker/deepstream:7.1-amd64-v3`
- **Measured Hardware Performance (from [`captured/speed_report.csv`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/speed_report.csv)):**
  - `yolo11s` (FP32): **30.75 FPS**, **32.53 ms** latency, **32.44 W** power, accuracy: *Not reported*
  - `best` PPE (FP32): **66.20 FPS**, **15.11 ms** latency, **32.87 W** power, accuracy: *Not reported*
- **Pipeline Outputs:**
  - Wire Telemetry: 395 MQTT messages published to broker topic `pipegen/detection/demo`
  - Metadata Log: `metadata.json` (872 KB per-frame structured detection & zone data)
  - DeepStream Export: Self-contained 26-file bundle under [`pipegen_export/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/pipegen_export/) and [`captured/export/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/export/) (`run.sh`, `manifest.json`, `PipelineIR.json`, C++ plugins, engine models)

---

## Mandatory Track A Requirement-to-Evidence Matrix

| Hackathon Requirement | Supporting Repo File / Evidence | Status | Notes |
|---|---|---|---|
| **1. Full PipeGen Flow**<br>*(Requirement &rarr; Pipeline IR &rarr; Model &rarr; Compiler &rarr; Run)* | [`docs/evidence/02_pipeline_ir_node_graph.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/02_pipeline_ir_node_graph.png)<br>[`docs/evidence/03_model_selection.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/03_model_selection.png)<br>[`docs/evidence/05_compile_both_engines.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/05_compile_both_engines.png)<br>[`docs/evidence/06_live_run_completed.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/06_live_run_completed.png) | **Verified** | Complete 5-stage progression captured directly from PipeGen GUI on RTX 3050 Laptop GPU. |
| **2. TensorRT Engine & Speed Report** | [`docs/evidence/04_speed_report_best_ppe_fp32.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/04_speed_report_best_ppe_fp32.png)<br>[`captured/speed_report.csv`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/speed_report.csv)<br>[`pipegen_export/models/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/pipegen_export/models/) | **Verified** | Real TensorRT FP32 engine compilation and layer speed profiling (15.11 ms, 66.2 FPS for PPE; 32.53 ms, 30.75 FPS for YOLO11s). |
| **3. Live Execution on Hardware** | [`docs/evidence/06_live_run_completed.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/06_live_run_completed.png)<br>[`docs/evidence/07_live_terminal_run_completed.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/07_live_terminal_run_completed.png)<br>[`captured/mqtt_sample.txt`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/mqtt_sample.txt)<br>[`captured/json_sample/metadata.json`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/json_sample/metadata.json) | **Verified** | Live run executed in Docker container `craftifaidocker/deepstream:7.1-amd64-v3` on RTX 3050 Laptop GPU processing 395 frames; terminal output confirmed 395 frames, 2,801 objects, 395 published MQTT messages (17.3 msg/s, 19.2s). |
| **4. Actionable Output Beyond Boxes** | [`docs/evidence/08_live_dashboard.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/08_live_dashboard.png)<br>[`backend/app/rules/engine.py`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/backend/app/rules/engine.py)<br>[`backend/app/api/incidents.py`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/backend/app/api/incidents.py)<br>[`frontend/src/routes/_authenticated/live.tsx`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/frontend/src/routes/_authenticated/live.tsx) | **Verified** | Raw per-frame bounding boxes are ingested into stateful, debounced safety incidents with Acknowledge and Resolve workflows, live SSE stream, real-time video feed, and live operator control room dashboard. |
| **5. Deep Integration**<br>*(PipeGen load-bearing, no perception code in app)* | [`backend/app/ingest/adapter.py`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/backend/app/ingest/adapter.py)<br>[`backend/app/main.py`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/backend/app/main.py) | **Verified** | Zero model inference code (`torch`, `cv2`, `tensorrt`, `onnxruntime`, `ultralytics`) exists in backend or frontend. All perception, tracking, and zone flags rely exclusively on PipeGen's DeepStream plugin outputs. |
| **6. Screenshots of IR Graph & Speed Report** | [`docs/evidence/02_pipeline_ir_node_graph.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/02_pipeline_ir_node_graph.png)<br>[`docs/evidence/04_speed_report_best_ppe_fp32.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/04_speed_report_best_ppe_fp32.png) | **Verified** | True interactive node graph and real TensorRT speed report screenshots included. |
| **7. Export Folder in Repository** | [`pipegen_export/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/pipegen_export/)<br>[`captured/export/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/export/) | **Verified** | Self-contained, relocatable export containing `run.sh`, `manifest.json`, `PipelineIR.json`, `models/`, `pipeline/configs/`, `pipeline/parsers/`, and `README.md`. |
| **8. Individual GUI Speed Card for `yolo11s`** | — | **Missing** | Succeeded in profiling and recorded in `captured/speed_report.csv`, but individual GUI card screenshot was not captured before stage progression. |
| **9. DeepStream Window Overlay Screenshot** | — | **Missing** | DeepStream was run headless with `fakesink` in Docker container; GUI window overlay screenshot was not captured. |

---

## How to Verify Locally

1. **Run End-to-End Replay Verification:**
   ```bash
   python scripts/e2e_check.py --replay
   # or: bash scripts/e2e_check.sh --replay
   ```
2. **Run Backend Test Suite:**
   ```bash
   cd backend && python -m pytest -q
   ```
3. **Run Frontend Tests and Production Build:**
   ```bash
   cd frontend && npm ci && npm run build && npx vitest run
   ```
