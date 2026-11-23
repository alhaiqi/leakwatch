# Progress

## 2026-11-23
- 19:31Z Phase 0 done. The only blocker was the auth-protected URL; the user made it public.
- 19:38Z Phase 1 done. Spikes in `spikes/`. Finding: a stopped service does not auto-start on request (DEBUG_LOG #1), so we use an always-on service (ADR-0003).
- 19:43Z Phase 2 done: 107 offline tests green, scanner coverage 98%, 0/30 flaky runs, 0 false positives on the placeholder fixtures.
- 19:48Z Phase 3 done: issue #1 opened masked, re-run deduped; 129 offline tests green; self-scan clean.
- 19:50Z Phase 4 done: live triage OK (placeholder 0.98, real 0.9), forced-failure fallback opened issue #2. 130 offline + 5 live tests green.
- 19:53Z Phase 5 done: service 'leakwatch' live on :8080, one hook, 401 on bad sig, push→issue in ~12 s, crash-restart proven. Sleep/wake only partially verified (ADR-0008).
- 19:58Z Phase 6 done: e2e passed 3× consecutively (plus one more pass before; one racy-oracle failure fixed, DEBUG_LOG #7).
- 20:02Z Phase 7 done: README, ARCHITECTURE, MANUAL_TEST (executed, 7/7 ✅), DEMO_SCRIPT, SUBMISSION, CLAUDE.md, references.
- 20:56Z **Final.** Phase 8 done: fresh clone from GitHub green (148 tests, 98% coverage, doctor 11/11); e2e 3× on final code; published to https://github.com/alhaiqi/leakwatch. DoD: all ✅ except sleep/wake, which is partially verified (human step in BLOCKED.md). Checkpoint v10 + milestone-8-green.
