# legacy_unverified/

Files moved here because they contain **unverified or fabricated PipeGen results**.

They remain in git history for reference, but are **not part of the submission**.

| File | Why quarantined |
|---|---|
| `tensorrt_speed_report.svg` | Hand-drawn SVG with hardcoded benchmark numbers (48.2 / 94.6 / 156.3 FPS) not produced by any real tool |
| `pipegen_ir_graph.svg` | Hand-drawn SVG pretending to be PipeGen IR; contains fabricated MQTT schema and benchmark numbers |
| `pipeline.json` | Contains an unverified `benchmarks` block with fabricated FPS/latency/power/mAP numbers |
| `run.sh` | References a `config/deepstream_app_config.txt` that does not exist; unverified |

When the real PipeGen export is available in `captured/export/`, it should be placed in
`pipegen_export/` and the matching evidence should go in `docs/evidence/`.
