#!/usr/bin/env bash
# ==============================================================================
# PipeGen v0.5.1 Generated DeepStream Pipeline Deployment Script
# Pipeline: SiteGuard Workplace Safety Sentinel
# Target: NVIDIA GPU (CUDA + TensorRT DeepStream)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CONFIG_FILE="${SCRIPT_DIR}/config/deepstream_app_config.txt"
OUTPUT_DIR="${PIPEGEN_OUTPUT_DIR:-/tmp/pipegen_out}"
MQTT_BROKER="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"

echo "===================================================================="
echo "🛡️  Starting SiteGuard PipeGen Pipeline (DeepStream 7.1)"
echo "   Config:  ${CONFIG_FILE}"
echo "   Broker:  ${MQTT_BROKER}:${MQTT_PORT}"
echo "   Output:  ${OUTPUT_DIR}"
echo "===================================================================="

mkdir -p "${OUTPUT_DIR}"

# Check for DeepStream runtime
if command -v deepstream-app >/dev/null 2>&1; then
    APP_BIN="deepstream-app"
else
    echo "⚠️  deepstream-app binary not found in PATH."
    echo "   Running inside PipeGen execution container..."
    APP_BIN="docker run --rm --gpus all --net=host -v ${SCRIPT_DIR}:/workspace -v ${OUTPUT_DIR}:/tmp/pipegen_out craftifaidocker/deepstream:7.1-amd64-v3 deepstream-app"
fi

exec ${APP_BIN} -c "${CONFIG_FILE}"
