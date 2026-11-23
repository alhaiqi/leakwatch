#!/usr/bin/env bash
# Spike: does a sprite-env service with --http-port 8080 (a) serve public traffic,
# (b) auto-restart on crash, (c) auto-start when stopped and a public request arrives?
set -u
URL=https://leakwatch-dev-bzxsz.sprites.app
st() { sprite-env services get spike | python3 -c 'import json,sys;s=json.load(sys.stdin)["state"];print("   state:",s["status"],"pid?",s.get("pid"),"restarts",s.get("restart_count"),s.get("error",""))'; }
svcpid() { ss -ltnp 2>/dev/null | grep ':8080 ' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }
sprite-env services delete spike >/dev/null 2>&1
sprite-env services create spike --cmd /usr/bin/python3 --args "$HOME/leakwatch/spikes/spike_service_app.py" --http-port 8080 --no-stream
sleep 3; echo "[a] running:"; curl -s $URL/; st
P=$(svcpid); echo "[b] crash: kill -9 $P"; kill -9 "$P"; sleep 4; curl -s -m 10 $URL/ || echo "   no answer"; st
echo "[c] stop, then public request"; sprite-env services stop spike; sleep 2; st
curl -s -m 30 -w "   (%{http_code}, %{time_total}s)\n" $URL/; st
