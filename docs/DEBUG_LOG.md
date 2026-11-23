# Debug log

## #1 — Stopped HTTP service does not auto-start on request (2026-11-23 19:34Z)
- **Hypothesis:** per `/.sprite/docs/services.md`, a service with `--http-port` auto-starts when a request arrives even if stopped.
- **Experiment:** `spikes/spike_service.sh` step [c]: `sprite-env services stop spike`, then `curl` the public URL. Retried 6× over 2 minutes.
- **Result:** first request 502 in 0.13 s; then 6 requests hung to the 20 s timeout. State stayed `failed / exited with code 143`. A manual `services start` restored a 200 immediately.
- **Best explanation:** auto-start probably applies when the *Sprite* boots or wakes, not to a service the user explicitly stopped (a stop records exit 143 = SIGTERM as "failed"). Two strikes; not pursued further because it isn't on the critical path.
- **Lesson:** never leave the LeakWatch service stopped; use `restart`. See ADR-0003.

## #2 — `pkill -f spike_service_app.py` killed my own shell (19:33Z)
- The harness shell's command line contained the same string. Fixed by killing the PID found on :8080 via `ss -ltnp`.
- **Lesson:** never `pkill -f` with a pattern that appears in your own command.

## #3 — Reasoning models return `content: null` with small `max_tokens` (preflight)
- `liquid/lfm-3-1.7b:free` with `max_tokens=10`: all tokens went to `message.reasoning`. With 400 it was fine.
- **Lesson:** triage uses `max_tokens≥800`, and if `content` is null it falls back to parsing JSON out of `reasoning`.

## #4 — Test over-constrained the PEM header (Phase 2)
- `test_raw_value_never_in_any_output` asserted that every fake value, including `FAKE_PEM_HEADER`, never appears. The header line (`-----BEGIN … PRIVATE KEY-----`) isn't secret: it's identical in every key file, and the issue *should* say what kind of key leaked.
- Fix: exempt only the header in that test. The key body is still asserted absent by `test_pem_finding_masked_without_body`. This is a corrected test, not a weakened one.

## #5 — Placeholder triage fell back to rules: "invalid JSON" (Phase 4)
- **Observed:** `test_placeholder_sk_your_key_here_is_not_real` got `source=rules (LLM output invalid)`.
- **Experiment:** printed the raw output of 3 preferred models for that prompt. `nemotron-3.5-lightning:free` returned a prose "thinking process" with JSON-ish fragments (the parser took the first `{`); `ling-3.2-flash:free` returned 429; `ernie-5.5-flash-preview:free` returned clean JSON (`placeholder`, 0.98).
- **Fixes:** (1) the parser takes the last decodable object containing `verdict`; (2) the malformed-retry goes to the next model; (3) ernie moved to first place; max_tokens raised to 1500.
- Also found a design gap: the LLM saw only `sk-y…re` and features claiming "no placeholder markers", so it couldn't judge. Features now include the locally computed `placeholder_marker` and word-segment counts (they don't reveal the value).
- **Result:** 5/5 live tests pass.

## #6 — Self-scan dirty after the Phase 4 commit (my own mistakes)
- **Observed:** `leakwatch self-scan` found 2 generic hits, but my gate command chain committed anyway, because `self-scan` wasn't part of the `&&` chain.
- (a) `spikes/phase3_seed.py`: `STRIPE_SECRET_KEY = "{fakes.stripe_live()}"` inside an f-string. The filter knew `{{…}}` but not single-brace interpolation. Added `{identifier…}` to the template markers (with a regression test).
- (b) `tests/unit/test_reporter.py`: I had typed a secret-shaped password literal into a test, against the "no secret-shaped literals" rule. Replaced it with `fakes.generic_password()`.
- **Lesson:** gate commits are now `pytest && self-scan && git commit`. milestone-4-green was re-tagged on the clean commit.
