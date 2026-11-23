"""Sprites API gateway: connection discovery + a thin HTTP client.

Credentials are injected by the gateway. This module refuses to send any Authorization header.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

GATEWAY_LIST = "https://api.sprites.dev/v1/gateway/list"
log = logging.getLogger("leakwatch.gateway")


class GatewayError(RuntimeError):
    pass


def _no_auth_header(request: httpx.Request) -> None:
    for h in ("authorization", "x-api-key", "proxy-authorization"):
        if h in request.headers:
            raise GatewayError(f"refusing to send {h} header: the gateway injects credentials")


class Gateway:
    def __init__(self, cache_file: Path | None = None, transport: httpx.BaseTransport | None = None,
                 timeout: float = 30):
        self.cache_file = cache_file
        self._conns: dict[str, dict] | None = None
        self.http = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False,
                                 event_hooks={"request": [_no_auth_header]},
                                 headers={"User-Agent": "leakwatch/0.1"})

    # ---- discovery ---------------------------------------------------------------------------
    def connections(self, refresh: bool = False) -> dict[str, dict]:
        if self._conns is not None and not refresh:
            return self._conns
        try:
            r = self.http.get(GATEWAY_LIST)
            r.raise_for_status()
            data = r.json()
            if self.cache_file:
                self.cache_file.write_text(json.dumps(data))
        except (httpx.HTTPError, ValueError) as e:
            if self.cache_file and self.cache_file.exists():
                log.warning("gateway list failed (%s); using cached discovery", type(e).__name__)
                data = json.loads(self.cache_file.read_text())
            else:
                raise GatewayError(f"cannot discover gateway connections: {e}") from e
        self._conns = {c["provider"]: c for c in data.get("connections", [])}
        return self._conns

    def base_url(self, provider: str) -> str:
        c = self.connections().get(provider)
        if not c:
            raise GatewayError(f"no '{provider}' connection; add it in the Sprites dashboard (Connectors)")
        return c["gateway_base_url"].rstrip("/")

    # ---- requests ----------------------------------------------------------------------------
    def request(self, provider: str, method: str, path: str, *, retries: int = 2, **kw) -> httpx.Response:
        url = self.base_url(provider) + "/" + path.lstrip("/")
        for attempt in range(retries + 1):
            try:
                r = self.http.request(method, url, **kw)
            except httpx.TransportError as e:
                if attempt == retries:
                    raise GatewayError(f"{method} {path}: {type(e).__name__}") from e
            else:
                if r.status_code in (502, 503, 504) and attempt < retries:
                    pass
                else:
                    if r.status_code in (401, 403) and provider != "openrouter":
                        log.error("gateway %s %s -> %s (check connector policy prefix 'leakwatch')",
                                  method, path, r.status_code)
                    return r
            time.sleep(1.5 * (attempt + 1))
        return r  # pragma: no cover
