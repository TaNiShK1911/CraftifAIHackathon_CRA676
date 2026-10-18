#!/usr/bin/env bash
# scripts/e2e_check.sh — End-to-end integration check script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Resolve Python executable
if [ -f "/c/Users/TANISHK JI/AppData/Local/Programs/Python/Python312/python.exe" ]; then
    PYTHON_BIN="/c/Users/TANISHK JI/AppData/Local/Programs/Python/Python312/python.exe"
elif command -v python3 &>/dev/null && python3 -V &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null && python -V &>/dev/null; then
    PYTHON_BIN="python"
elif command -v py &>/dev/null; then
    PYTHON_BIN="py -3"
else
    echo "Python 3 is required but not found in PATH." >&2
    exit 1
fi

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" scripts/e2e_check.py "$@"
