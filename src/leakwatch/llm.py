"""OpenRouter via the Sprites gateway — FREE models only, with 429 fallback across models."""
from __future__ import annotations

import logging
import os
import time

import httpx

from .gateway import Gateway, GatewayError

log = logging.getLogger("leakwatch.llm")


class LLMUnavailable(RuntimeError):
    pass


class OpenRouter:
    def __init__(self, gw: Gateway, preferred: list[str], max_models: int = 4, timeout: float = 45,
                 max_tokens: int = 900):
        self.gw, self.preferred, self.max_models = gw, preferred, max_models
        self.timeout, self.max_tokens = timeout, max_tokens
        self._models: list[str] | None = None
        self._models_at = 0.0
        self.last_model: str | None = None

    def free_models(self, refresh: bool = False) -> list[str]:
        forced = os.environ.get("LEAKWATCH_LLM_FORCE_MODELS")  # test hook: e.g. a nonexistent model
        if forced:
            return [m.strip() for m in forced.split(",") if m.strip()]
        if self._models is not None and not refresh and time.time() - self._models_at < 3600:
            return self._models
        r = self.gw.request("openrouter", "GET", "/v1/models", retries=1)
        if r.status_code != 200:
            raise LLMUnavailable(f"/v1/models -> {r.status_code}")
        free = [m["id"] for m in r.json().get("data", []) if str(m.get("id", "")).endswith(":free")]
        ordered = [m for m in self.preferred if m in free] + [m for m in free if m not in self.preferred]
        self._models, self._models_at = ordered, time.time()
        return ordered

    def complete(self, messages: list[dict], models: list[str] | None = None) -> tuple[str, str]:
        """Return (text, model). Tries free models in order; raises LLMUnavailable if all fail."""
        try:
            candidates = models or self.free_models()
        except (GatewayError, httpx.HTTPError) as e:
            raise LLMUnavailable(f"model list: {e}") from e
        errors = []
        for model in candidates[: self.max_models]:
            if not model.endswith(":free"):  # hard guard: never a paid model
                errors.append(f"{model}: not free, skipped")
                continue
            try:
                r = self.gw.request("openrouter", "POST", "/v1/chat/completions", retries=0,
                                    timeout=self.timeout,
                                    json={"model": model, "messages": messages, "temperature": 0,
                                          "max_tokens": self.max_tokens})
            except (GatewayError, httpx.HTTPError) as e:
                errors.append(f"{model}: {type(e).__name__}")
                continue
            if r.status_code != 200:
                errors.append(f"{model}: HTTP {r.status_code}")
                continue
            try:
                msg = r.json()["choices"][0]["message"]
            except (ValueError, KeyError, IndexError):
                errors.append(f"{model}: bad response shape")
                continue
            text = msg.get("content") or msg.get("reasoning") or ""
            if not text.strip():
                errors.append(f"{model}: empty content")
                continue
            self.last_model = model
            return text, model
        log.warning("all free models failed: %s", "; ".join(errors))
        raise LLMUnavailable("; ".join(errors) or "no free models")
