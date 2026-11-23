# Progress

## 2026-11-23
- 19:31Z Phase 0 done. The only blocker was the auth-protected URL; the user made it public.
- 19:38Z Phase 1 done. Spikes in `spikes/`. Finding: a stopped service does not auto-start on request (DEBUG_LOG #1), so we use an always-on service (ADR-0003).
- 19:43Z Phase 2 done: 107 offline tests green, scanner coverage 98%, 0/30 flaky runs, 0 false positives on the placeholder fixtures.
- 19:48Z Phase 3 done: issue #1 opened masked, re-run deduped; 129 offline tests green; self-scan clean.
- 19:50Z Phase 4 done: live triage OK (placeholder 0.98, real 0.9), forced-failure fallback opened issue #2. 130 offline + 5 live tests green.
