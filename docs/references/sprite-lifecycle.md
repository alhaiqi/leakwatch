# Source: /.sprite/llm.txt lines 70-90 (Lifecycle + Services), saved 2026-11-23

- Validate and sanitize all inputs
- Use proper error handling that doesn't leak internal paths or stack traces
- Never hardcode secrets - use environment variables and never expose them via HTTP

## Lifecycle
- Sprites run while actively servicing HTTP requests
- Sprites run while detachable sessions are generating output
- When neither condition is true, sprites pause
- Sprites may remain paused or be fully stopped at any time
- When stopped, detachable sessions are lost
- Services restart automatically at boot time

## Services
- Long-running processes that persist between reboots
- Managed through the internal API via `sprite-env services` or the socket API
- Automatically restarted when sprite boots
- One service can have an `http_port` configured to receive proxied HTTP requests
- HTTP service auto-starts when proxy receives a request

## Checkpoints
- Point-in-time checkpoints and restores available

# Note from user (2026-11-23): `sprite url update --auth public` works but is deprecated in favor of `sprite config update --url-auth public`.
