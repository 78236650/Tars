"""Role-based tool permission checker — v4.0.0 Phase 1 Task 11.

Loads tool_permissions.yaml and provides permission checks for tool dispatch.
"""
import yaml
from pathlib import Path
from typing import Optional


class ToolPermissionChecker:
    """Checks whether a user role can use a specific tool."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path] = None) -> dict:
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "tool_permissions.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def can_use_tool(self, role: str, tool_name: str) -> bool:
        """Return True if the role can use the given tool."""
        role_config = self._config.get("roles", {}).get(role, {})

        # admin: allow everything by default
        if role == "admin":
            return True

        allowed = role_config.get("allowed_tools", [])
        if allowed == "*":
            return True

        denied = role_config.get("denied_tools", [])
        # Explicit deny overrides
        if tool_name in denied:
            return False

        return tool_name in allowed

    def has_workspace_restriction(self, role: str) -> bool:
        """Return True if the role has workspace path restrictions."""
        role_config = self._config.get("roles", {}).get(role, {})
        return role_config.get("workspace_restriction", True)

    def get_allowed_tools(self, role: str) -> Optional[list[str]]:
        """Return the list of allowed tools for a role, or None for all."""
        role_config = self._config.get("roles", {}).get(role, {})
        allowed = role_config.get("allowed_tools", [])
        if allowed == "*" or role == "admin":
            return None  # None means all allowed
        return allowed


# ── Global singleton ────────────────────────────────────────────────

tool_permission_checker = ToolPermissionChecker()
