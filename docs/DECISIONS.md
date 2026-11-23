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
