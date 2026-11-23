# Preflight — Phase 0 (2026-11-23)

All commands were run from inside the Sprite. Raw outputs are summarized here; the redacted gateway list is in `references/gateway-list.json`.

| Check | Result | Status |
|---|---|---|
| Inside a Sprite | `sprite-env info` → name `leakwatch-dev`, id `sprite-3c530420-…`, env version 0.0.5 | ✅ |
| Public URL | `https://leakwatch-dev-bzxsz.sprites.app` | ⚠️ **auth-protected**: unauthenticated GET returns `302 → https://sprites.dev/auth/sprite?...` (tested with a server on :8080). GitHub webhooks can't follow this. |
| Gateway list | 2 connections: `github` (oauth, `alhaiqi`, scopes `read:org,repo`, policy `name_prefix=leakwatch`) and `openrouter` (api_key/BYOK, policy `name_prefix=leakwatch`) | ✅ |
| GitHub `GET /user` | 200, login `alhaiqi`, `x-oauth-scopes: read:org, repo`, rate limit 4996 remaining | ✅ |
| Test repo `alhaiqi/leakwatch-playground` | exists, `private: true`, default branch `main`, admin permission, issues enabled, 0 hooks | ✅ |
| Submission repo `alhaiqi/leakwatch` | exists, `private: false`, admin permission, size 0 (empty) | ✅ |
| OpenRouter `GET /v1/models` | 441 models, 12 ending in `:free` (list below) | ✅ |
| OpenRouter chat completion | `liquid/lfm-3-1.7b:free` → 200 in 0.72 s, `usage.cost: 0`. **Gotcha:** it's a reasoning model. With `max_tokens=10` it returned `content: null` (all tokens spent on `reasoning`); with 400 it returned `"OK"` (46 tokens). `nvidia/nemotron-3.5-lightning:free` → 200; `google/gemma-4-31b-it:free` → 429 | ✅ |
| Tooling | Python 3.13.17, pip 26.3, git 2.53.0, gh 2.79.0 (not logged in), sqlite3 3.46.1 | ✅ |
| `sprite-env` | present at `/.sprite/bin/sprite-env`. Subcommands: `info`, `services` (create with `--http-port`, which auto-starts the service when a request arrives), `checkpoints` (create/list/restore), `curl`. No `tasks` subcommand. | ✅ |
| Services | none defined yet | — |
| Checkpoints | `v1` "initial checkpoint" (19:12Z) | ✅ |

Free models at preflight time: `inclusionai/ling-3.2-flash:free`, `baidu/ernie-5.5-flash-preview:free`, `liquid/lfm-3-1.7b:free`, `particle-ai/particle-1:free`, `recursive/flint-v1.0:free`, `nvidia/nemotron-3.5-super-vl:free`, `dots-studio/dots-3-note-preview:free`, `nvidia/nemotron-3.5-lightning:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `google/gemma-4-26b-a4b-it:free`, `google/gemma-4-31b-it:free`.

OpenRouter response shape: OpenAI-compatible `choices[0].message.content` (it can be `null`, in which case the text sits in `message.reasoning`), and `usage.cost`.

## Issues found

1. **Public URL requires Sprite auth (302 to the login page).** The webhook path needs the URL set to public. The local `sprite-env` API has no URL-settings endpoint (`/v1/url`, `/v1/config` and `/v1/info` all return 404). This needs a human with the `sprite` CLI or the dashboard. See the question in the Phase 0 message.
2. Prompt inconsistency: the safety rules say push with `gh`, but the verified facts say `gh` is not logged in, so the push goes through the Git Data API via the connector. The facts win (ADR-0002).
