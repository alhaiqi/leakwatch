# Architecture Decision Records

## ADR-0001 — Phase 0 answers (2026-11-23)
**Context:** The prompt pre-answered the Phase 0 questions.
**Decision:** Watch only `alhaiqi/leakwatch-playground` (private test repo). The submission repo is `alhaiqi/leakwatch` (public). Issues use the deadpan "security uncle" tone.
**Consequences:** The allowlist in `config/leakwatch.toml` contains the test repo only.

## ADR-0002 — Publish via the Git Data API, not `gh` (2026-11-23)
**Context:** The safety rules say "push using `gh`", but the verified facts say `gh` is not logged in and the push should go through the GitHub connector.
**Options:** (a) ask the user to run `gh auth login`; (b) blobs → tree → commit → ref through the gateway.
**Decision:** (b). It needs no token on disk, and it's consistent with the project's "no stored tokens" story.
**Consequences:** A small `scripts/publish.py` is required. It only writes to `alhaiqi/leakwatch`, and only after the self-scan is clean.

## ADR-0003 — Supervision: always-on `sprite-env` service on :8080 (2026-11-23)
**Context:** The server has to stay reachable for webhooks and survive crashes, sleep and wake. The Sprite has no systemd (see `references/sprite-services.md`). The docs make two claims: a service with `--http-port` "auto-starts when a request arrives, even if stopped", and "services keep the sprite alive".
**Evidence:** `spikes/spike_service.sh` and `spikes/spike_service_output.txt`:
- public request → service on :8080: **200** ✅
- `kill -9` of the service process: restarted within about 4 s with a new PID ✅ (state `running`, restart_count 1)
- `services stop`, then a public request: **502**, then **hangs for 20 s** six times in a row; the service never auto-started ❌ (it contradicts the docs; see DEBUG_LOG #1)
- manual `services start` recovered it ✅
**Options:** (a) rely on auto-start on request (disproved for a stopped service); (b) an always-on service plus crash-restart plus boot-restart; (c) polling mode.
**Decision:** (b). `leakwatch serve` runs as service `leakwatch` with `--http-port 8080`. It's never "stopped" by our tooling; deploys use `services restart`. The server writes a heartbeat line every 30 s (`data/heartbeat.log`: wall clock, PID, boot_id), so pauses (wall-clock gaps, same PID) and reboots (new boot_id) are *observed*, not assumed. `leakwatch doctor` summarizes them.
**Consequences:** Per the docs a running service keeps the Sprite awake. That costs more than a sleeping Sprite, but it's what makes delivery reliable. A paused VM resumes the same process, and a stopped VM restarts services at boot. GitHub retries undelivered webhooks are not guaranteed, so missed deliveries are covered by `scan-recent` (manual) and redelivery from the hook's delivery log.

## ADR-0004 — Free-model fallback order (2026-11-23)
**Evidence:** `spikes/spike_b_output.txt`: 10 of 12 `:free` models returned valid JSON in 0.5–2.1 s; both Gemma models returned 429.
**Decision:** At startup fetch `/v1/models` and keep only ids ending in `:free` (hard guard: a non-`:free` id is never sent). Order: preferred list from config (`nvidia/nemotron-3.5-lightning:free`, `inclusionai/ling-3.2-flash:free`, `baidu/ernie-5.5-flash-preview:free`, `liquid/lfm-3-1.7b:free`), then any other free model. On a 429, 5xx or timeout, try the next one; after 4 failed models, use rules-only triage.

## ADR-0005 — Dedupe lives only in SQLite; no fingerprint in issue bodies (2026-11-23)
**Context:** We could put the fingerprint in each issue as a hidden marker, so dedupe would survive a DB loss.
**Decision:** No. sha256(repo+file+secret) of a *weak* password can be brute-forced from a public hash. Dedupe uses an atomic `INSERT OR IGNORE` claim in `data/leakwatch.db` (mode 600). The claim is released if issue creation fails.
**Consequences:** Wiping `data/` means already-reported secrets can be reported again. That's acceptable for a personal tool.

## ADR-0006 — A low-confidence LLM "placeholder" can't suppress a known-format hit (2026-11-23)
**Context:** Free models can be wrong, and a missed real leak costs more than an extra issue.
**Decision:** For known-format regex hits, an LLM `placeholder` verdict with confidence < `llm_placeholder_min_confidence` (0.7) becomes `unsure`, and is reported when rule confidence ≥ 0.8. For generic hits the LLM verdict is final.

## ADR-0007 — Orchestration lives in `reporter.py` (2026-11-23)
**Context:** The prompt fixes the folder layout. `Pipeline.process_commit` (fetch → scan → triage → decide → issue) needs a home.
**Decision:** `reporter.py`, rather than adding a module outside the layout. Rotation steps: the LLM's steps when it returns 2–8 valid ones, otherwise the curated per-type steps.

## ADR-0008 — Sleep/wake: what is proven and what is not (2026-11-23)
**Context:** Gate 5 asks that the server survive a Sprite sleep/wake cycle.
**What the docs say:** `services.md` says a running service keeps the Sprite from pausing; `llm.txt` says Sprites pause when they aren't serving HTTP or producing session output, and services restart at boot.
**Proven here:** crash → auto-restart (kill -9, back in under 5 s); `services restart` is clean; the public URL reaches the service; the service is registered, so per the docs it restarts at boot.
**Not observable from inside this session:** a real pause. This Claude Code console session is attached and producing output, so the Sprite can't pause while I work, and a checkpoint restore (which restarts the environment) would kill this session.
**Decision:** Keep the always-on service (ADR-0003). The heartbeat log (`data/heartbeat.log`, summarized by `leakwatch doctor`) gives post-hoc evidence of any pause (a wall-clock gap with the same PID) or reboot (a new boot_id). `scripts/sleepwake_check.sh` is a human step: after the console is closed and the Sprite has been idle, push a commit and confirm the issue appears; doctor then shows the gap/reboot counts.
**Consequences:** The DoD item "survives a sleep/wake cycle" is marked **partially verified** until that check runs. That's stated in the final summary, not glossed over.
