"""Spike (a): GitHub call through the Sprites gateway — no token anywhere."""
import json, urllib.request
gw = json.load(urllib.request.urlopen("https://api.sprites.dev/v1/gateway/list"))
base = next(c["gateway_base_url"] for c in gw["connections"] if c["provider"] == "github")
with urllib.request.urlopen(base + "/user") as r:
    print("GET /user", r.status, json.load(r)["login"], "scopes:", r.headers.get("x-oauth-scopes"))
with urllib.request.urlopen(base + "/repos/alhaiqi/leakwatch-playground/commits?per_page=1") as r:
    c = json.load(r)[0]; print("latest commit", c["sha"][:10], c["commit"]["message"][:40])
