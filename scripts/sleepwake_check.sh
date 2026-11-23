#!/usr/bin/env bash
# Human step (ADR-0008): run AFTER the Sprite has been idle (console closed) for 10+ minutes.
# From your laptop:   sprite console -s leakwatch-dev   then:   bash ~/leakwatch/scripts/sleepwake_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== heartbeat (gaps = pauses, new boot_id = reboot)"
.venv/bin/python -c "import sys;sys.path.insert(0,'src');from leakwatch.cli import heartbeat_summary;from pathlib import Path;print(heartbeat_summary(Path('data/heartbeat.log')))"
echo "== service + health"
sprite-env services get leakwatch; echo
curl -s https://"$(sprite-env info | python3 -c 'import json,sys;print(json.load(sys.stdin)["sprite_url"].split("//")[1])')"/healthz; echo
echo "== push a fake key and wait for the issue"
.venv/bin/python scripts/demo_seed.py leak --wait 90
