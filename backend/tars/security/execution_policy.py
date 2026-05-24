"""Execution policy — which tools require human approval before running."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "execution_policy.yaml"


class ExecutionPolicy:
    def __init__(self, config_path: Optional[Path] = None):
        self._config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path] = None) -> dict[str, Any]:
        path = config_path or DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @property
    def approval_config(self) -> dict[str, Any]:
        return dict(self._config.get("approval", {}))

    @property
    def enabled(self) -> bool:
        return bool(self.approval_config.get("enabled", True))

    @property
    def timeout_seconds(self) -> int:
        return int(self.approval_config.get("timeout_seconds", 300))

    def requires_approval(
        self,
        tool_name: str,
        arguments: Optional[dict] = None,
        user_role: str = "user",
    ) -> bool:
        if not self.enabled:
            return False
        auto_roles = self.approval_config.get("auto_allow_for_roles", [])
        if user_role in auto_roles:
            return False
        required = self.approval_config.get("require_for_tools", [])
        return tool_name in required


execution_policy = ExecutionPolicy()
