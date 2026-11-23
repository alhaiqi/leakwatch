#!/usr/bin/env bash
# Health check: config, connectors, service, public URL, webhook, heartbeat.
cd "$(dirname "$0")/.." && exec .venv/bin/leakwatch doctor "$@"
