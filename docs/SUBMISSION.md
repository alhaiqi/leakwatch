# Submission drafts

**Deadline:** midnight PST, Sunday Nov 29, 2026 (= Monday Nov 30, 10:00 in Beirut).

## X / Twitter (255 characters + a 23-character link = 278, under 280)

> LeakWatch 🔑 an agent on a @flydotio Sprite that watches my private GitHub pushes, lets a free LLM (masked values only) sort real leaks from placeholders, and opens one masked issue with rotation steps. No tokens on disk: Sprites Connectors. #Hacksgiving <DEMO_LINK>

## LinkedIn

> For Fly.io's #Hacksgiving I built **LeakWatch**, a small personal agent that runs on a Fly.io Sprite and watches my private GitHub repos for leaked secrets.
>
> Why: GitHub's free push protection covers public repos and known token formats. Private repos and plain passwords or connection strings fall through the gap, and AI-assisted commits leak secrets at about twice the usual rate (GitGuardian, State of Secrets Sprawl 2026).
>
> How it works: a push webhook reaches the Sprite, which reads the diff through the Sprites **GitHub connector** and scans only the added lines with format rules plus entropy. A free LLM via the **OpenRouter connector**, which only ever sees masked values, separates real leaks from placeholders. LeakWatch then opens one masked issue with rotation steps, and never the same one twice.
>
> The part I like most: there's no API token anywhere on the machine. The connectors inject credentials at the gateway.
>
> Code: https://github.com/alhaiqi/leakwatch · Demo: <DEMO_LINK> @Fly.io

## Form answers

- **Project name:** LeakWatch
- **Code link:** https://github.com/alhaiqi/leakwatch
- **Demo link:** `<DEMO_LINK>` (record it with docs/DEMO_SCRIPT.md)
- **Short description:** LeakWatch is a personal agent on a Fly.io Sprite that watches pushes to private GitHub repos for leaked secrets. It scans only the added lines with format rules and an entropy check. A free LLM, which sees masked values only, separates real leaks from placeholders, and LeakWatch then opens one masked issue per leak with rotation and history-purge steps. It uses two Sprites connectors (GitHub and OpenRouter), so no token ever lives on the Sprite.
- **Sprites features used:** Sprite public URL plus webhook, `sprite-env` services (supervised, crash-restart), checkpoints, Connectors gateway (GitHub OAuth and OpenRouter) with name-prefix access policies.
- **Built this week:** yes. The git history (and the `milestone-*-green` tags) runs from Nov 23, 2026.
