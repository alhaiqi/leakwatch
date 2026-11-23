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

## #7 — e2e run 1: "expected exactly 2 issues, got 1" (Phase 6)
- **Observed:** the service log shows *both* findings reported (`AKIA…` at 19:55:09, `database_url` at 19:55:14). The e2e listed issues at 19:55:17 and saw one.
- **Hypothesis:** GitHub's `GET /repos/{o}/{r}/issues?labels=` list is eventually consistent and lags new issues by seconds.
- **Fix:** the e2e takes the issue set from the server's own DB (`fingerprints.issue_url` for the commit SHA; `processed` is written only after all issues exist), then fetches each with `GET /issues/{n}`, which is consistent. LeakWatch itself was correct; the test's oracle was racy. No assertion was weakened.

## #8 — Flaky tests found by the fresh-clone check (Phase 8)
- **Observed:** in `/tmp/lw-fresh`, 1 of the first runs failed; 40 reruns gave 2 failures (`test_all_true_positives_detected`, `test_random_vs_word`). The 30× check in Phase 2 had seen 0, consistent with a ~1% rate.
- **Hypothesis:** `fakes.generic_password()` (18 chars) sometimes has entropy < 3.5 because of repeated characters, so the detector correctly drops it.
- **Experiment:** 100k samples: P(entropy < 3.5) = **0.64%** at 18 chars, 0.002% at 24, 0.0000% at 28.
- **Fix:** the fake generic password is 28 chars. The 3.5 threshold is unchanged (it's in the spec). Not a weakened test: the fixture now represents a secret that the spec says must be caught.
- **Product consequence:** documented in README Limitations: short random passwords can fall under the threshold.

## #9 — A secret-shaped (made-up) literal lives in published history
- The first Phase 4 commit (local `7ea83ae`, public `a1766f1`) contains the test password literal from #6, fixed in the next commit. It's a random string I invented for a unit test, not a credential for anything. Removing it from public history would need a force-push, which the safety rules forbid. HEAD scans clean (`publish.py` enforces that).
- **Follow-up (same hunt):** after the 28-char fix there was still about 1 failure in 100–150 suites. Captured: `test_scrub_masks_unknown_high_entropy_tokens`. `scrub()` required digits+letters, so a random 32-char token with no digits (~0.36% of draws) went unmasked. **That was a product gap**, since letters-only random keys exist. `scrub()` now masks any token of 24+ chars with entropy ≥ 3.5 unless it's a plain-word snake/kebab/dotted identifier. Its generic rule also skips dotted identifiers and paths, matching the detector. Cost: long camelCase identifiers get masked in log/LLM context.
- Then 0/200 failures. One more suspected source, a timing race: `test_healthz_and_heartbeat` asserted the heartbeat file existed before the scheduled task had necessarily run. Now it waits up to 2 s.

## #10 — Strict placeholder filter dropped ~1 in 20k random known-format keys (Phase 8)
- **Found by:** 1/200 failure of `test_prompt_never_contains_raw_secret` (no finding at all). Fuzzing the test logic 50k times reproduced it once; fuzzing `placeholder_reason(strict=True)` over 5×100k fakes showed `mask-chars` (`x{4,}` case-insensitive, 3–6 hits per 100k) and 5-letter words (`fixme`, `dummy`).
- **This was a real false negative:** a real key with `XXXX` or `DUMMY` in its random part would have been silently dropped.
- **Fix:** for known formats, mask runs must be ≥8 (≥12 for zeros) and only placeholder words of 7+ letters count. Regression tests: 7 formats × 5000 random keys must all pass; obvious placeholders (`AKIA` + 16 X, `ghp_` + 36 x, `…EXAMPLE…`, `REDACTED`, `****`, all-zero) must still be caught.
- Self-correction: my first version of that test contained AWS's published example key as a literal, which breaks the safety rules. I replaced it with a runtime-built value before committing.
- **Second pass:** the new regression test still failed sometimes. Fuzzing 7×100k found `getenv` (case-insensitive) inside a random anthropic key and `your_` inside an `sk-proj-` key. In strict mode, env lookups now need real syntax (`getenv(`, `os.environ`…; tokens can't contain `(` or `.`) and `your` must be followed by a lowercase word (`your-key`). **Result: 0 drops in 1.05M random keys**, and `sk-proj-your-key-goes-here…` is still caught.
- Stability after all fixes: **0/100** full-suite failures (148 tests per run); fuzz: 0 strict-filter drops in 2.1M random keys.

## #11 — Broken gate: `grep CLEAN` matched "NOT CLEAN"
- My gate chain `self-scan | tail -1 | grep CLEAN` passed on `… -> NOT CLEAN`, so a commit landed with a secret-shaped test literal (`sk-proj-YOUR_key…`, a made-up OpenAI-format string). `publish.py`'s own guard refused to push it, so it never reached the public repo.
- Fix: the literal is built at runtime, and gates now use `leakwatch self-scan` **exit code** (1 when anything is found). The earlier gates (Phases 4–7) printed `CLEAN` in their output, so they weren't affected.
