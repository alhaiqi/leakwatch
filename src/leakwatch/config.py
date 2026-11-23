"""Configuration loading (TOML) + paths."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    repos: list[str]
    report_unsure_min_confidence: float = 0.8
    llm_placeholder_min_confidence: float = 0.7
    llm_enabled: bool = True
    preferred_models: list[str] = field(default_factory=list)
    max_models_to_try: int = 4
    llm_timeout: float = 45
    llm_max_tokens: int = 900
    tone: str = "security-uncle"
    labels: list[str] = field(default_factory=lambda: ["leakwatch"])
    port: int = 8080
    heartbeat_seconds: int = 30
    data_dir: Path = ROOT / "data"

    def is_watched(self, repo: str) -> bool:
        return repo.lower() in {r.lower() for r in self.repos}


def load(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("LEAKWATCH_CONFIG") or ROOT / "config" / "leakwatch.toml")
    raw = tomllib.loads(path.read_text())
    w, t, l, i, s = (raw.get(k, {}) for k in ("watch", "thresholds", "llm", "issues", "server"))
    cfg = Config(
        repos=list(w.get("repos", [])),
        report_unsure_min_confidence=float(t.get("report_unsure_min_confidence", 0.8)),
        llm_placeholder_min_confidence=float(t.get("llm_placeholder_min_confidence", 0.7)),
        llm_enabled=bool(l.get("enabled", True)),
        preferred_models=list(l.get("preferred_models", [])),
        max_models_to_try=int(l.get("max_models_to_try", 4)),
        llm_timeout=float(l.get("timeout_seconds", 45)),
        llm_max_tokens=int(l.get("max_tokens", 900)),
        tone=str(i.get("tone", "security-uncle")),
        labels=list(i.get("labels", ["leakwatch"])),
        port=int(s.get("port", 8080)),
        heartbeat_seconds=int(s.get("heartbeat_seconds", 30)),
        data_dir=Path(os.environ.get("LEAKWATCH_DATA") or ROOT / "data"),
    )
    if os.environ.get("LEAKWATCH_DISABLE_LLM") == "1":
        cfg.llm_enabled = False
    return cfg


def ensure_data_dir(cfg: Config) -> Path:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(cfg.data_dir, 0o700)
    return cfg.data_dir
