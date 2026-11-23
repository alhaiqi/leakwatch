# Demo script (75–90 s)

**Setup before recording:** in the Sprite console run `scripts/doctor.sh` and confirm it's all green. Open three windows: (A) terminal in `~/leakwatch`, (B) the browser on `github.com/alhaiqi/leakwatch-playground/issues`, (C) optionally `tail -f /.sprite/logs/services/leakwatch.log`.

| Time | Shot | Narration |
|---|---|---|
| 0:00–0:08 | Title card: "LeakWatch 🔑" over the playground repo | "GitHub only blocks leaked secrets for free on *public* repos. My private repos? On their own." |
| 0:08–0:18 | Window A: `scripts/doctor.sh` scrolling green | "LeakWatch is a tiny agent on a Fly.io Sprite. It has no tokens on disk: GitHub and the LLM come through Sprites Connectors." |
| 0:18–0:28 | A: `.venv/bin/python scripts/demo_seed.py leak --wait 90` | "I push a commit with an AWS key. It's fake, generated on the spot." |
| 0:28–0:38 | C: log lines `queued 1 commit(s)` → `verdict real (llm:…:free)` | "GitHub's webhook wakes the Sprite's server. It scans only the added lines, and a free LLM, which only ever sees the masked value, confirms it's real." |
| 0:38–0:55 | B: refresh. The issue appears; click it. **Zoom** on `AKIA…xx` in the table, then on "Rotate it" and "purge from history" | "Seconds later: one issue. The key is masked, first four and last two characters. Here's exactly how to rotate it, and how to scrub it from history. And the security uncle has opinions." (Linger on the uncle line.) |
| 0:55–1:08 | A: `demo_seed.py placeholder --wait 60` → `no new issue`; then `demo_seed.py duplicate --wait 60` → `dup=1, no new issue` | "A placeholder like `your-api-key-here`? Nothing. The same key pushed again? Still one issue, because it's deduped by a hash, never by the secret." |
| 1:08–1:20 | Closing card with the mermaid diagram from the README | "LeakWatch: one job, done reliably. Running on a Fly.io Sprite, with Sprites Connectors for GitHub and OpenRouter. Built for Hacksgiving." |

**After recording:** `.venv/bin/python scripts/demo_seed.py cleanup`.

**Fallbacks while recording:** if the issue takes longer than about 30 s, cut the wait in editing (usual latency is 6–27 s, see TEST_REPORT). If the LLM is rate-limited, the issue says "rules-only" and still appears.
