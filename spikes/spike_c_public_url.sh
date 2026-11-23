#!/usr/bin/env bash
# Spike (c): does an unauthenticated public request reach a process on :8080?
set -u
URL=$(sprite-env info | python3 -c 'import json,sys;print(json.load(sys.stdin)["sprite_url"])')
python3 -m http.server 8080 --directory "$(mktemp -d)" >/tmp/spike_c.log 2>&1 &
PID=$!; sleep 1.5
curl -s -o /dev/null -w "GET $URL/ -> %{http_code} in %{time_total}s\n" "$URL/"
curl -s -o /dev/null -w "POST $URL/hook -> %{http_code}\n" -X POST "$URL/hook" -d '{}'
kill $PID; echo "--- server log:"; cat /tmp/spike_c.log
