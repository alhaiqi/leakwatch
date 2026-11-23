#!/usr/bin/env bash
# Live end-to-end run against the private test repo (needs the 'leakwatch' service running).
# Cleanup always runs: e2e.py cleans up in `finally`; this trap covers a killed interpreter.
set -uo pipefail
cd "$(dirname "$0")/.."
trap '.venv/bin/python scripts/e2e.py --cleanup-only' EXIT
.venv/bin/python scripts/e2e.py
