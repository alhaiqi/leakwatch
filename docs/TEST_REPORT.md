# Test report

## Phase 3 gate: scan-commit on a real commit (2026-11-23T19:48:21Z)
- Seeded commit `2bef8fc9ed0b2ed58d67245e4e17646bcd9f8240` on branch `leakwatch-e2e-phase3-1795463237` (fake AWS key generated at runtime, `spikes/phase3_seed.py`).
- Run 1, `LEAKWATCH_DISABLE_LLM=1 leakwatch scan-commit … --ref leakwatch-e2e-phase3-1795463237`: `findings=1 new_issues=1 duplicates=0 in 4.56s`, which opened https://github.com/alhaiqi/leakwatch-playground/issues/1
- Verified through the API: title `🔑 Possible leaked AWS access key ID in app/settings.py:4`, labels `leakwatch, leakwatch-e2e`, **raw key in issue: False**, masked `AKIA…N3` present.
- Run 2 (same commit): `findings=1 new_issues=0 duplicates=1`, so **no duplicate**.
- The DB holds only the SHA-256 fingerprint (`5d47f9dcf8e4…`), file, type and issue URL.

## Phase 4 gate: LLM triage (2026-11-23T19:50:32Z)
- `pytest -m live tests/integration`: **5 passed**.
  - `sk-your-key-here` → `placeholder`, confidence 0.98, source `llm:baidu/ernie-5.5-flash-preview:free`
  - random fake AWS key → `real`, confidence 0.9 (LLM)
  - only `:free` models listed; GitHub gateway smoke OK; a forced-bad model raises `LLMUnavailable`
- Triage JSON validation: 11 offline tests (valid, fenced, think-then-answer, 9 malformed shapes, retry-once, double-malformed → rules, unavailable → rules, LLM output scrubbed).
- **Forced failure, live:** `LEAKWATCH_LLM_FORCE_MODELS=leakwatch/does-not-exist:free leakwatch scan-commit … 0861a151da906990bf438c1271ded6cd007ea06e`: OpenRouter returned `HTTP 400` → rules-only → the 0.95-confidence Stripe key was still reported at https://github.com/alhaiqi/leakwatch-playground/issues/2

## Phase 5 gate: webhook + service (2026-11-23T19:53:57Z)
- `register-webhook` run twice: `created hook 715896002`, then `updated hook 715896002`. Doctor reports `1 hook(s)`, i.e. exactly one.
- Bad signature on the public URL: `POST /github/webhook` with `sha256=deadbeef` → **401**.
- GitHub's hook-creation ping → **200** (the signature verified with the stored secret).
- **Real push → automatic issue:** commit `b6246cdf427fd3b77276ffe83521bd771665f9f8` pushed at 19:52:18Z on `leakwatch-e2e-aws-1795463535`; webhook `202 Accepted` at 19:52:17.996Z (the contents API commit and the delivery arrived together); LLM verdict `real (llm:baidu/ernie-5.5-flash-preview:free)`; issue visible through the API at 19:52:31Z (about 12 s).
- Crash recovery of the real service: `kill -9 3698` → restarted with pid 3709 within 5 s; `/healthz` 200; state `running`, restart_count 1. The heartbeat log recorded both restarts.
- `leakwatch doctor --deep`: **12/12 green**.
- 144 offline tests green. (One upstream `StarletteDeprecationWarning` about httpx in TestClient; harmless.)
