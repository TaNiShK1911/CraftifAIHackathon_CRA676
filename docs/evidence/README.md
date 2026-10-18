# Evidence Directory (`docs/evidence/`)

This directory contains real visual evidence captured directly from the CraftifAI PipeGen GUI running on an **NVIDIA GeForce RTX 3050 Laptop GPU** (WSL2 Ubuntu 24.04, Docker container `craftifaidocker/deepstream:7.1-amd64-v3`).

## Evidence Index

| File | What It Really Shows | Requirement Supported | Status |
|---|---|---|---|
| [`02_pipeline_ir_node_graph.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/02_pipeline_ir_node_graph.png) | Interactive Node Graph in PipeGen showing the full DAG: Input (`demo.mp4`) &rarr; Preprocess &rarr; Inference (YOLO11s Person + YOLOv8n PPE) &rarr; Postprocess &rarr; Custom (Hungarian tracking, Hazard zone alert with polygon, PPE violation alert) &rarr; Output (MQTT `pipegen/detection/demo` + JSON) | Mandatory Track A: Pipeline IR Graph | **Verified** |
| [`02_pipeline_ir_node_graph_upper.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/02_pipeline_ir_node_graph_upper.png) | Zoomed detail of upper DAG: Input file reading `demo.mp4`, parallel preprocessing letterboxing, and parallel inference nodes (YOLO11s COCO person detector + YOLOv8n 6-class PPE detector) | Supplementary Track A: Pipeline IR Graph Detail | **Verified** |
| [`02_pipeline_ir_node_graph_lower.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/02_pipeline_ir_node_graph_lower.png) | Zoomed detail of lower DAG: Postprocess decoding &rarr; Hungarian person tracking &rarr; Hazard zone alert (marked polygon) &rarr; PPE violation alert &rarr; Output nodes (MQTT single + JSON single) | Supplementary Track A: Pipeline IR Graph Detail | **Verified** |
| [`03_model_selection.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/03_model_selection.png) | PipeGen Model stage / Deep Search matching `yolo11s.onnx` (RestrictedAreaMonitoring) and `best.onnx` (ppe-kit) | Mandatory Track A: Model Selection & Catalog | **Verified** |
| [`04_speed_report_best_ppe_fp32.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/04_speed_report_best_ppe_fp32.png) | Real TensorRT speed report for `best.onnx` (PPE detector) compiled to FP32: 196 TRT layers, 1.98 ms initial layers, 3.75 ms middle layers, 8.72 ms final layers (total 14.47 ms layer sum / 15.11 ms trtexec end-to-end, ~66.2 FPS, 32.87 W) | Mandatory Track A: TensorRT Engine & Speed Report | **Verified** |
| [`05_compile_both_engines.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/05_compile_both_engines.png) | PipeGen Compiler stage showing both FP32 TensorRT engines bound to inference nodes (`node 3 -> yolo11s.fp32.plan`, `node 6 -> best.fp32.plan`) and "Pipeline compiled successfully" | Mandatory Track A: Compiler Stage & Engine Binding | **Verified** |
| [`06_live_run_completed.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/06_live_run_completed.png) | Live run completion status ("Pipeline run completed") with export trigger button | Mandatory Track A: Live Run & Export Trigger | **Verified** |
| [`07_live_terminal_run_completed.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/07_live_terminal_run_completed.png) | Terminal output of live `./run.sh` execution on target device: 395 frames, 2,801 objects, 395 published MQTT messages (17.3 msg/s, 19.2s runtime) with results in `out/` | Mandatory Track A: Live Hardware Execution | **Verified** |
| [`08_live_dashboard.png`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/docs/evidence/08_live_dashboard.png) | SiteGuard Live Monitoring dashboard at `http://localhost:5173/live` streaming live video feed (`cam0`), green `[LIVE · SSE]` status, `[BROKER ✓]`, `LIVE: 38` badge, live KPI breakdown, and real-time incident counters (`[✓ LIVE ONLY]`) | Actionable Output & Deep Integration: Live Operator Dashboard | **Verified** |

## Missing / Incomplete Visual Evidence
1. **Speed-report screenshot for `yolo11s`**: While `yolo11s` was compiled and profiled on-device (metrics recorded in [`captured/speed_report.csv`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/captured/speed_report.csv) and `ModelStage.json`), a screenshot of its individual layer-breakdown card in the GUI was not captured before moving to the next stage.
2. **DeepStream graphical window overlay**: DeepStream was run with `fakesink` inside the container; a screenshot of an X11 graphical rendering window overlay was not captured.

## Quarantined Legacy Assets (`legacy_unverified/`)
All hand-drawn SVGs and pre-run seeded dashboard screenshots have been moved out of this directory to [`legacy_unverified/`](https://github.com/TaNiShK1911/CraftifAIHackathon_CRA676/blob/main/legacy_unverified/):
- `legacy_unverified/pipegen_ir_graph.svg` (Hand-drawn SVG)
- `legacy_unverified/tensorrt_speed_report.svg` (Hand-drawn SVG)
- `legacy_unverified/01_live_dashboard.png` through `05_system_diagnostics.png` (Screenshots displaying synthetic seed data, quarantined to preserve strict provenance)
