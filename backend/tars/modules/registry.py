"""Module Registry — v4.0.0 Phase 4.

Loads module switches from modules.yaml, provides enable/disable checks.
Controls which subsystems are initialized at startup.
"""
import yaml
from pathlib import Path


class ModuleRegistry:
    """Reads config/modules.yaml and exposes enable/disable checks."""

    CORE_MODULES = ("auth", "chat", "memory", "skills", "tools", "knowledge")
    OPTIONAL_MODULES = ("bi", "meeting", "admin", "cron", "insight", "orchestration", "presales")

    def __init__(self):
        self._modules: dict[str, bool] = {}
        self._requires: dict[str, tuple[str, ...]] = {}
        self._default_enabled = True

    def _read_optional_enabled(self, config: dict, module_name: str) -> bool | None:
        """Parse flat or nested modules.yaml (modules.optional.meeting.enabled)."""
        modules = config.get("modules") or {}
        if not isinstance(modules, dict):
            return None

        flat = modules.get(module_name)
        if isinstance(flat, bool):
            return flat

        optional = modules.get("optional")
        if isinstance(optional, dict):
            entry = optional.get(module_name)
            if isinstance(entry, dict) and "enabled" in entry:
                return bool(entry["enabled"])
            if isinstance(entry, bool):
                return entry
        return None

    def _read_optional_meta(self, config: dict, module_name: str) -> dict:
        modules = config.get("modules") or {}
        if not isinstance(modules, dict):
            return {}
        optional = modules.get("optional")
        if isinstance(optional, dict):
            entry = optional.get(module_name)
            if isinstance(entry, dict):
                return entry
        return {}

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
                    enabled = self._read_optional_enabled(config, m)
                    self._modules[m] = (
                        enabled if enabled is not None else self._default_enabled
                    )
                    meta = self._read_optional_meta(config, m)
                    req = meta.get("requires")
                    if isinstance(req, list):
                        self._requires[m] = tuple(str(x) for x in req)
            except Exception:
                # On parse error, enable all optional modules
                for m in self.OPTIONAL_MODULES:
                    self._modules[m] = True

    def is_enabled(self, module_name: str) -> bool:
        """Return True if the module is enabled."""
        return self._modules.get(module_name, self._default_enabled)

    def get_requires(self, module_name: str) -> tuple[str, ...]:
        return self._requires.get(module_name, ())

    def check_dependencies(self, module_name: str) -> tuple[bool, str]:
        """Return (ok, message) for optional module dependencies."""
        if not self.is_enabled(module_name):
            return False, f"模块 '{module_name}' 未启用"
        for dep in self.get_requires(module_name):
            if not self.is_enabled(dep):
                return False, f"模块 '{module_name}' 依赖 '{dep}' 未启用"
        return True, ""

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
