# Evidence Directory (`docs/evidence/`)

This directory contains visual evidence for the SiteGuard submission.

## 1. Verified Dashboard UI Evidence (Included)
These screenshots document the running web dashboard and its provenance mechanisms:
- `01_live_dashboard.png` — Real-time live monitor feed, video panel, and incident stats
- `02_incidents_management.png` — Incidents table with status tracking and acknowledge/resolve workflow
- `03_pipeline_and_evidence.png` — Pipeline status and edge optimization overview
- `04_tensorrt_benchmarks.png` — Precision comparison table and latency breakdown view
- `05_system_diagnostics.png` — Real-time system health and broker telemetry

## 2. PipeGen Pipeline Execution Evidence (Captured from GPU)
Per hackathon rules, these files must be real captures from a local PipeGen run (not fabricated SVGs):
- `01_requirement.png` — PipeGen Requirement stage screenshot
- `02_pipeline_ir_graph.png` — PipeGen Pipeline IR node graph (MANDATORY)
- `03_model_selection.png` — PipeGen Model catalog / Deep Search selection
- `04_tensorrt_speed_fp16.png` — TensorRT FP16 speed report (MANDATORY)
- `05_tensorrt_speed_int8.png` — TensorRT INT8 speed report (Edge Optimization BONUS)
- `06_live_run.png` — Live run terminal output + DeepStream window screenshot

> Fabricated hand-drawn SVGs (`pipegen_ir_graph.svg`, `tensorrt_speed_report.svg`) have been quarantined to `legacy_unverified/` and are not used for evidence.
