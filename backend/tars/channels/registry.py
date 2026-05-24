"""Configuration-driven channel registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "channels.yaml"


class ChannelRegistry:
    """Loads channel configuration from YAML."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ChannelRegistry":
        path = config_path or DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        else:
            raw = {}
        return cls(raw)

    @property
    def use_router(self) -> bool:
        return bool(self.config.get("channels", {}).get("use_router", True))

    def list_adapters(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.config.get("channels", {}).get("adapters", {}))

    def is_adapter_enabled(self, adapter_id: str) -> bool:
        entry = self.list_adapters().get(adapter_id, {})
        return bool(entry.get("enabled", True))
