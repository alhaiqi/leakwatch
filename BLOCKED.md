# Human-only steps (nothing blocks the build)

LeakWatch is built, deployed, tested and published. These steps need a human:

1. **Verify sleep/wake (≈15 min, mostly waiting).** Close every `sprite console` session to the Sprite and leave it idle for 10+ minutes. Then `sprite console -s leakwatch-dev` and run `bash ~/leakwatch/scripts/sleepwake_check.sh`. It prints the heartbeat pause/reboot counts and pushes a fake key; expect an issue within about 60 s. If the issue doesn't arrive, run `sprite-env services restart leakwatch` and see ADR-0003/0008; the fallback is `leakwatch serve --poll 60`.
2. **Record the demo** with `docs/DEMO_SCRIPT.md` (run `scripts/doctor.sh` first, then `scripts/demo_seed.py cleanup` afterwards). Add the video link to README.md ("Demo video") and docs/SUBMISSION.md.
3. **Post** the X/LinkedIn text in docs/SUBMISSION.md (tag @flydotio, #Hacksgiving).
4. **Submit the form** before **midnight PST, Sun Nov 29** (10:00 Mon Nov 30, Beirut) with the answers in docs/SUBMISSION.md.
5. Optional: after editing README with the demo link, republish with `.venv/bin/python scripts/publish.py alhaiqi/leakwatch` (commit first).
