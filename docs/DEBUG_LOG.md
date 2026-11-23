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
