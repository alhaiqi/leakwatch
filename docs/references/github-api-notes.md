# GitHub REST API: behaviour relied on (saved 2026-11-23)

Sources: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries ·
https://docs.github.com/en/rest/commits/commits#get-a-commit ·
https://docs.github.com/en/rest/git · https://docs.github.com/en/rest/repos/webhooks

- Webhook signature: header `X-Hub-Signature-256: sha256=<hex HMAC-SHA256 of the raw body, keyed with the hook secret>`. Compare in constant time.
- `GET /repos/{o}/{r}/commits/{sha}` returns `files[]` with a unified-diff `patch` (hunks only). `patch` is omitted for binary or very large files; at most 300 files.
- Creating a hook sends a `ping` event (observed: 200 from our server at 19:52:02Z).
- The Git Data API (blobs/trees/commits/refs) does **not** work on an empty repository (409 "Git Repository is empty"); the first commit has to come from the contents API. Observed in Phase 8, see DEBUG_LOG.
- **Observed (DEBUG_LOG #7):** `GET /repos/{o}/{r}/issues?labels=…` can lag newly created issues by a few seconds; `GET /repos/{o}/{r}/issues/{n}` is consistent.
- `x-oauth-scopes` response header lists the connector token's scopes (`read:org, repo`). `repo` covers hooks on repos you admin.
