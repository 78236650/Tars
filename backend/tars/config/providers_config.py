"""Provider configuration loader — v4.1.0"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG: Optional[Dict[str, Any]] = None


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "providers.yaml"


def _expand_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1], "")
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_providers_config() -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults: Dict[str, Any] = {
        "default_provider": "ollama-local",
        "providers": {},
        "fallback": {
            "enabled": False,
            "chain": [],
            "retry_on": [429, 500, 502, 503, 504, "timeout"],
            "max_attempts": 3,
        },
    }

    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            merged = {**defaults, **_expand_env(raw)}
            if "fallback" in raw:
                merged["fallback"] = {**defaults["fallback"], **_expand_env(raw["fallback"])}
            _CONFIG = merged
            return _CONFIG
        except Exception as e:
            print(f"[ProvidersConfig] 加载失败，使用默认: {e}")

    _CONFIG = defaults
    return _CONFIG
