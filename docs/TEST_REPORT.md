# Test report

## Phase 3 gate: scan-commit on a real commit (2026-11-23T19:48:21Z)
- Seeded commit `2bef8fc9ed0b2ed58d67245e4e17646bcd9f8240` on branch `leakwatch-e2e-phase3-1795463237` (fake AWS key generated at runtime, `spikes/phase3_seed.py`).
- Run 1, `LEAKWATCH_DISABLE_LLM=1 leakwatch scan-commit … --ref leakwatch-e2e-phase3-1795463237`: `findings=1 new_issues=1 duplicates=0 in 4.56s`, which opened https://github.com/alhaiqi/leakwatch-playground/issues/1
- Verified through the API: title `🔑 Possible leaked AWS access key ID in app/settings.py:4`, labels `leakwatch, leakwatch-e2e`, **raw key in issue: False**, masked `AKIA…N3` present.
- Run 2 (same commit): `findings=1 new_issues=0 duplicates=1`, so **no duplicate**.
- The DB holds only the SHA-256 fingerprint (`5d47f9dcf8e4…`), file, type and issue URL.
