# LeakWatch: rules for future sessions

LeakWatch is a personal secret-leak watcher running on the Fly.io Sprite `leakwatch-dev`. Keep it small: one job, done reliably. No dashboard, history scanning, auto-rotation or multi-user support.

## Absolute rules
- **No credentials anywhere.** All external calls go through `https://api.sprites.dev/v1/gateway/<provider>/<id>/…`; discover IDs via `/v1/gateway/list`, never hardcode them. Never add an Authorization header (`gateway.py` refuses to).
- **Never use real secrets.** Test secrets come from `tests/fakes.py` at runtime. Fixtures use `{{FAKE_*}}` tokens. No secret-shaped literals in this repo: `leakwatch self-scan` must print CLEAN before any commit or push.
- **Masked values only** in issues, logs, DB (SHA-256 fingerprints), test output and LLM prompts. The LLM never sees the raw value.
- **LLM: only model ids ending in `:free`** (hard guard in `llm.py`).
- **Write scope:** only repos in `config/leakwatch.toml`. Allowed writes: issues and labels, the one LeakWatch webhook, branches prefixed `leakwatch-e2e-` (and test commits on them), closing issues labelled `leakwatch-e2e`. Never delete repos, force-push, rewrite history, change repo settings, or touch anything not created by LeakWatch.
- The submission repo `alhaiqi/leakwatch` is updated only by `scripts/publish.py` (Git Data API via the connector), after a clean self-scan.

## Working rules
- Test-first. Gate commits: `pytest && leakwatch self-scan && git commit`. Never weaken or skip a test to go green; if a test was wrong, fix it and explain why in `docs/DEBUG_LOG.md`.
- Record decisions as ADRs in `docs/DECISIONS.md` and dead ends in `docs/DEBUG_LOG.md` (hypothesis → experiment → result → lesson). Three strikes on one approach: stop, go back to the last `milestone-*-green` tag, pick an alternative and write an ADR.
- Don't `pkill -f` with a pattern that appears in your own command line (DEBUG_LOG #2).

## Operations
- Service: `sprite-env services get|restart leakwatch` (never `stop`: a stopped service does **not** auto-start on request, DEBUG_LOG #1). Logs: `/.sprite/logs/services/leakwatch.log`.
- Health: `.venv/bin/leakwatch doctor --deep`. Live tests: `pytest -m live`, `scripts/e2e.sh`.
- Checkpoint after milestones: `sprite-env checkpoints create --comment "…"`.
