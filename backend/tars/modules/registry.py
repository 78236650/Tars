"""Module Registry — v4.0.0 Phase 4.

Loads module switches from modules.yaml, provides enable/disable checks.
Controls which subsystems are initialized at startup.
"""
import yaml
from pathlib import Path


class ModuleRegistry:
    """Reads config/modules.yaml and exposes enable/disable checks."""

    CORE_MODULES = ("auth", "chat", "memory", "skills", "tools", "knowledge")
    OPTIONAL_MODULES = ("bi", "meeting", "admin", "cron")

    def __init__(self):
        self._modules: dict[str, bool] = {}
        self._default_enabled = True

    def load(self, config_path: str = None):
        """Load module switches from modules.yaml."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "modules.yaml"

        # Core modules always on
        for m in self.CORE_MODULES:
            self._modules[m] = True

        if Path(str(config_path)).exists():
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
                self._default_enabled = config.get("default_enabled", True)
                for m in self.OPTIONAL_MODULES:
                    self._modules[m] = config.get("modules", {}).get(m, self._default_enabled)
            except Exception:
                # On parse error, enable all optional modules
                for m in self.OPTIONAL_MODULES:
                    self._modules[m] = True

    def is_enabled(self, module_name: str) -> bool:
        """Return True if the module is enabled."""
        return self._modules.get(module_name, self._default_enabled)

    def list_modules(self) -> list[dict]:
        """List all modules with their enabled status."""
        result = []
        for name in self.CORE_MODULES + self.OPTIONAL_MODULES:
            result.append({
                "name": name,
                "enabled": self._modules.get(name, True),
                "type": "core" if name in self.CORE_MODULES else "optional",
            })
        return result


# ── Global singleton ────────────────────────────────────────────────

module_registry = ModuleRegistry()
