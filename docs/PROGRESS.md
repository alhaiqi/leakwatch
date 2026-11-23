# Progress

## 2026-11-23
- 19:31Z Phase 0 done. The only blocker was the auth-protected URL; the user made it public.
- 19:38Z Phase 1 done. Spikes in `spikes/`. Finding: a stopped service does not auto-start on request (DEBUG_LOG #1), so we use an always-on service (ADR-0003).
- 19:43Z Phase 2 done: 107 offline tests green, scanner coverage 98%, 0/30 flaky runs, 0 false positives on the placeholder fixtures.
