"""Spike (b): OpenRouter chat completion via the gateway, free models only, 429 fallback."""
import json, time, urllib.request, urllib.error
gw = json.load(urllib.request.urlopen("https://api.sprites.dev/v1/gateway/list"))
base = next(c["gateway_base_url"] for c in gw["connections"] if c["provider"] == "openrouter")
free = [m["id"] for m in json.load(urllib.request.urlopen(base + "/v1/models"))["data"] if m["id"].endswith(":free")]
print(len(free), "free models")
for m in free:
    body = json.dumps({"model": m, "max_tokens": 600, "messages": [{"role": "user", "content": 'Return only JSON: {"ok": true}'}]}).encode()
    req = urllib.request.Request(base + "/v1/chat/completions", body, {"Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
        msg = d["choices"][0]["message"]
        print(f"{m}: 200 {time.time()-t:.1f}s content={str(msg.get('content'))[:60]!r} cost={d['usage'].get('cost')}")
    except urllib.error.HTTPError as e:
        print(f"{m}: HTTP {e.code}")
    except Exception as e:
        print(f"{m}: {type(e).__name__} {e}")
