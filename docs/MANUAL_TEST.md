# Manual test (about 10 minutes)

Run inside the Sprite (`sprite console -s leakwatch-dev`), from `~/leakwatch`. All secrets are fakes generated at runtime.

| # | Step | Expected result | Actual result (executed 2026-11-23 ~20:00Z by Claude) |
|---|---|---|---|
| 1 | `scripts/doctor.sh` | Every line ✅; last line `doctor: N/N checks green` | ✅ `doctor: 11/11 checks green` (config, no tokens in env, data perms 700/600, gateway, GitHub connector, repo private, free models, service running, `/healthz` 200, 1 webhook, heartbeat) |
| 2 | `.venv/bin/python scripts/demo_seed.py leak --wait 90` | Pushes a fake AWS key on a `leakwatch-e2e-demo-*` branch; prints `issues=1` and an issue URL within about 60 s | ✅ `processed after 6s: findings=1 issues=1 dup=0`, which opened https://github.com/alhaiqi/leakwatch-playground/issues/14 |
| 3 | Open the issue URL | Title `🔑 Possible leaked AWS access key ID in app/settings.py:4`. The secret is shown as `AKIA…xx` (first 4 + last 2), never in full. "Rotate it" and "purge from history" sections present. Security-uncle line at the top | ✅ Title as expected; checked through the API against the committed file: **full key present: False**, masked `AKIA…YQ` present: True; verdict `real · LLM triage · confidence 0.95`; both sections present |
| 4 | `.venv/bin/python scripts/demo_seed.py placeholder --wait 60` | Commits `config.example.env` (`API_KEY=your-api-key-here`, `PASSWORD=changeme`); prints `no new issue` | ✅ `findings=0 issues=0`, `no new issue` |
| 5 | `.venv/bin/python scripts/demo_seed.py duplicate --wait 60` | Re-adds the same key line in a new commit; prints `dup=1` and `no new issue` | ✅ `findings=1 issues=0 dup=1`, `no new issue` |
| 6 | `curl -s -X POST https://<sprite-url>/github/webhook -H 'X-GitHub-Event: push' -H 'X-Hub-Signature-256: sha256=0000' -d '{}'` | HTTP 401 `{"error":"invalid signature"}` | ✅ `{"error":"invalid signature"} -> HTTP 401` |
| 7 | `.venv/bin/python scripts/demo_seed.py cleanup` | Closes the demo issue(s) and deletes the demo branch | ✅ `closed …/issues/14`, `deleted branch leakwatch-e2e-demo-20261123-200015` |

Optional, after the Sprite has been idle (ADR-0008): `scripts/sleepwake_check.sh`. It prints the pause/reboot counts from the heartbeat log, then pushes a fake key and waits for the issue. **Not executed yet:** it needs the console closed so the Sprite can actually go idle.
