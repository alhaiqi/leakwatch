# Source: `sprite --help`, `sprite url --help`, `sprite url update --help`, `sprite config update --help` (sprite CLI 0.0.5, run inside leakwatch-dev), saved 2026-11-23

```
Command "update" is deprecated, use 'sprite config update --url-auth' instead
sprite url update - Update URL authentication settings

...
sprite config update - Update sprite configuration

Usage:
  sprite config update [flags] [sprite-name]

Flags:
  -o, --org <name>       Specify organization
  -s, --sprite <name>    Specify sprite
  --url-auth <type>      URL authentication type: 'public' or 'sprite'
  --private-access <type>  Private URL access type: 'admins' or 'org_users'
  --label <label>        Label to apply to the sprite (can be repeated)
  --clear-labels         Clear all existing labels before applying --label
```

- Inside the Sprite the CLI is installed but **not logged in** (`sprite list` → "no organizations configured. Run 'sprite login'"). URL auth must be changed from a machine where `sprite login` was done (e.g. your laptop).
- Verified working on 2026-11-23 (by the user, from their laptop): `sprite url update --auth public -s leakwatch-dev` → `Auth: public`. The `sprite config update --url-auth public -s leakwatch-dev` form is the documented replacement; same flags per its help.
