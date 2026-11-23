# Submission drafts

**Deadline:** midnight PST, Sunday Nov 29, 2026 (= Monday Nov 30, 10:00 in Beirut).

**One-liner:** A personal security agent you own: it watches your private repos for leaked keys, runs on your own Sprite, and holds zero credentials itself.

## X / Twitter (250 characters + a 23-character link = 273, under 280)

> LeakWatch 🔑 a security agent you own: watches your private repos for leaked keys, runs on your own @flydotio Sprite, holds zero credentials (Sprites Connectors). The LLM only sees masked snippets; you get plain-language rotation steps. #Hacksgiving <DEMO_LINK>

## LinkedIn

> For Fly.io's #Hacksgiving I built **LeakWatch**: a personal security agent you own. It watches my private GitHub repos for leaked keys, runs on my own Fly.io Sprite, and holds **zero credentials** itself.
>
> Why I wanted it: commits co-authored by Claude Code leak secrets at about twice the baseline rate, and 64% of secrets confirmed valid in 2022 were still exploitable in early 2026 (GitGuardian, State of Secrets Sprawl 2026). GitHub's push protection for users is on by default only for public repos.
>
> What makes it different:
> • **Self-hosted:** diffs are scanned on my Sprite, so no third-party scanner reads my code. The LLM only ever sees masked snippets (`AKIA…XY`).
> • **Zero stored credentials:** GitHub and OpenRouter access go through **Sprites Connectors**, which inject credentials at the gateway. There's no token on the machine to steal.
> • **LLM triage:** a free model separates real keys from placeholders like `your-api-key-here`.
> • **Plain-language rotation steps** in one masked issue per leak, and never the same one twice.
>
> To be clear about the alternatives: GitGuardian's free tier (individuals and teams under 25) and GitHub Secret Protection are far more complete, and a pre-commit hook (gitleaks or ggshield) is the best place to stop a leak. LeakWatch is for people who want a small watcher they own and run themselves.
>
> Code: https://github.com/alhaiqi/leakwatch · Demo: <DEMO_LINK> @Fly.io

## Form answers

- **Project name:** LeakWatch
- **Code link:** https://github.com/alhaiqi/leakwatch
- **Demo link:** `<DEMO_LINK>` (record it with docs/DEMO_SCRIPT.md)
- **Short description:** A personal security agent you own: LeakWatch watches your private GitHub repos for leaked keys, runs on your own Fly.io Sprite, and holds zero credentials itself. GitHub and OpenRouter access go through Sprites Connectors. Diffs are scanned on the Sprite (format rules plus entropy); a free LLM that sees only masked snippets separates real keys from placeholders. Each real leak gets one masked issue with plain-language rotation and history-purge steps.
- **Sprites features used:** Sprite public URL plus webhook, `sprite-env` services (supervised, crash-restart), checkpoints, Connectors gateway (GitHub OAuth and OpenRouter) with name-prefix access policies.
- **Built this week:** yes. The git history (and the `milestone-*-green` tags) runs from Nov 23, 2026.
