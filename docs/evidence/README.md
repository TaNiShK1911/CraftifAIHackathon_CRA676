# Evidence Directory (`docs/evidence/`)

This directory contains real visual evidence for the SiteGuard submission.

## 1. Verified Dashboard UI Evidence
These screenshots document the running web dashboard and its provenance mechanisms:
- [`01_live_dashboard.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/01_live_dashboard.png) — Real-time live monitor feed, video panel, and incident stats
- [`02_incidents_management.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/02_incidents_management.png) — Incidents table with status tracking, provenance chip, and acknowledge/resolve workflow
- [`03_pipeline_and_evidence.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/03_pipeline_and_evidence.png) — Pipeline status and edge optimization overview
- [`04_tensorrt_benchmarks.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/04_tensorrt_benchmarks.png) — Precision comparison table and latency breakdown view
- [`05_system_diagnostics.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/05_system_diagnostics.png) — Real-time system health and broker telemetry

## 2. PipeGen Pipeline Execution Evidence (Captured Live from GPU)
Captured from live execution of CraftifAI PipeGen inside Docker (`craftifaidocker/deepstream:7.1-amd64-v3`) running on NVIDIA GeForce RTX 3050 Laptop GPU (CUDA 13.1, Driver 591.74):
- [`pipegen_02_pipeline_ir_graph.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/pipegen_02_pipeline_ir_graph.png) — PipeGen Pipeline IR node graph generated from English prompt with hazard zone polygon
- [`pipegen_03_model_selection.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/pipegen_03_model_selection.png) — PipeGen Deep Search model selection matching person detector (`yolo11s.onnx`) and PPE detector (`best.onnx`)
- [`pipegen_04_tensorrt_speed_report.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/pipegen_04_tensorrt_speed_report.png) — TensorRT engine compilation and speed report on RTX 3050
- [`pipegen_05_pipeline_compilation.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/pipegen_05_pipeline_compilation.png) — DeepStream pipeline compilation output and binding of compiled `.plan` engines
- [`pipegen_06_live_run.png`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/docs/evidence/pipegen_06_live_run.png) — Completed pipeline execution (395 frames, 2801 objects processed) and export trigger

> Note: All legacy unverified SVGs were moved to [`legacy_unverified/`](file:///c:/Users/TANISHK%20JI/OneDrive/Desktop/SiteGuard/legacy_unverified/). Every screenshot in this directory is a genuine PNG captured from actual software execution.
