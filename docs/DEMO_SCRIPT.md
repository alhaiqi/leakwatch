# Demo script (75–90 s)

**Setup before recording:** in the Sprite console run `scripts/doctor.sh` and confirm it's all green. Open three windows: (A) terminal in `~/leakwatch`, (B) the browser on `github.com/alhaiqi/leakwatch-playground/issues`, (C) optionally `tail -f /.sprite/logs/services/leakwatch.log`.

| Time | Shot | Narration |
|---|---|---|
| 0:00–0:08 | Title card: "LeakWatch 🔑: a security agent you own" over the playground repo | "This is LeakWatch: a personal security agent I own. It watches my private repos for leaked keys, runs on my own Sprite, and holds zero credentials itself." |
| 0:08–0:18 | Window A: `scripts/doctor.sh` scrolling green; pause on "no tokens in environment ✅" | "No GitHub token, no API key on this machine. GitHub and the LLM come through Sprites Connectors, which add the credentials at the gateway." |
| 0:18–0:28 | A: `.venv/bin/python scripts/demo_seed.py leak --wait 90` | "I push a commit with an AWS key. It's fake, generated on the spot." |
| 0:28–0:38 | C: log lines `queued 1 commit(s)` → `verdict real (llm:…:free)` | "The webhook hits my Sprite. The diff is scanned right here, so no third-party scanner reads my code. A free LLM sees only a masked snippet and confirms it's a real key, not a placeholder." |
| 0:38–0:55 | B: refresh. The issue appears; click it. **Zoom** on `AKIA…xx` in the table, then on "Rotate it" and "purge from history" | "Seconds later: one issue. The key is masked. Plain-language steps to rotate it, then how to scrub it from history. And the security uncle has opinions." (Linger on the uncle line.) |
| 0:55–1:08 | A: `demo_seed.py placeholder --wait 60` → `no new issue`; then `demo_seed.py duplicate --wait 60` → `dup=1, no new issue` | "A placeholder like `your-api-key-here`? Nothing. The same key pushed again? Still one issue, because it's deduped by a hash, never by the secret." |
| 1:08–1:20 | Closing card with the mermaid diagram from the README | "A security agent you own: on your own Fly.io Sprite, zero credentials thanks to Sprites Connectors. Already using GitGuardian or a pre-commit hook? Keep it. LeakWatch is the small watcher you run yourself. Built for Hacksgiving." |

**After recording:** `.venv/bin/python scripts/demo_seed.py cleanup`.

**Fallbacks while recording:** if the issue takes longer than about 30 s, cut the wait in editing (usual latency is 6–27 s, see TEST_REPORT). If the LLM is rate-limited, the issue says "rules-only" and still appears.
