# pipegen_export/

This folder should contain the **real PipeGen export** — the pipeline definition
and generated `run.sh` from CraftifAI PipeGen.

## Current status: EMPTY — awaiting real export

The previous contents were moved to `legacy_unverified/` because they contained
unverified benchmark numbers and referenced files that do not exist.

## What belongs here

Once you have run PipeGen on the GPU machine, copy the export folder here:

```bash
cp -r /path/to/pipegen/export/* pipegen_export/
```

Expected files:
- `pipeline.json` — the real PipeGen pipeline definition (no hand-edited benchmarks)
- `run.sh` — the generated DeepStream launch script
- Any config files PipeGen generates (e.g., `config/deepstream_app_config.txt`)
