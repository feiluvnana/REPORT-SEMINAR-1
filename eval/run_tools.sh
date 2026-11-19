#!/usr/bin/env bash
# Thin wrapper: the implementation lives in run_tools.py (portable).
# Usage: bash REPORT/eval/run_tools.sh [--skip-hash-check] [--tools ...] [--docs ...] [--repeats N]
set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="$ROOT/.venv/Scripts/python.exe"
[[ -x "$PY" ]] || PY="$(command -v python3 || command -v python)"
exec "$PY" "$SCRIPT_DIR/run_tools.py" "$@"
