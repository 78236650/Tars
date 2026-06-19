"""Module Registry — v5.3.0 two-layer architecture.

Loads module switches from modules.yaml, provides enable/disable checks.
"""
import yaml
from pathlib import Path


class ModuleRegistry:
    """Reads config/modules.yaml and exposes enable/disable checks."""

    CORE_MODULES = ("auth", "chat", "memory", "skills", "tools", "wiki")
    OPTIONAL_MODULES = (
        "bi", "meeting", "admin", "cron", "insight", "orchestration",
        "presales", "governance", "report", "semantic",
        "vessel_plan", "wind_stowage", "skillhub",
    )
    LAYER1_MODULES = frozenset({
        "meeting", "skillhub", "orchestration", "presales",
        "vessel_plan", "wind_stowage", "wiki", "chat", "memory", "tools", "skills",
    })
    LAYER2_MODULES = frozenset({
        "bi", "insight", "governance", "report", "semantic",
    })

    def __init__(self):
        self._modules: dict[str, bool] = {}
        self._requires: dict[str, tuple[str, ...]] = {}
        self._layers: dict[str, int] = {}
        self._default_enabled = True

    def _read_optional_enabled(self, config: dict, module_name: str) -> bool | None:
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
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "modules.yaml"

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
                    layer = meta.get("layer")
                    if isinstance(layer, int):
                        self._layers[m] = layer
            except Exception:
                for m in self.OPTIONAL_MODULES:
                    self._modules[m] = True

    def is_enabled(self, module_name: str) -> bool:
        return self._modules.get(module_name, self._default_enabled)

    def get_requires(self, module_name: str) -> tuple[str, ...]:
        return self._requires.get(module_name, ())

    def get_layer(self, module_name: str) -> int | None:
        if module_name in self.LAYER1_MODULES:
            return self._layers.get(module_name, 1)
        if module_name in self.LAYER2_MODULES:
            return self._layers.get(module_name, 2)
        return None

    def get_modules_by_layer(self, layer: int) -> list[str]:
        names = self.LAYER1_MODULES if layer == 1 else self.LAYER2_MODULES
        return [m for m in names if self.is_enabled(m)]

    def check_dependencies(self, module_name: str) -> tuple[bool, str]:
        if not self.is_enabled(module_name):
            return False, f"模块 '{module_name}' 未启用"
        for dep in self.get_requires(module_name):
            if dep == "knowledge":
                dep = "wiki"
            if not self.is_enabled(dep):
                return False, f"模块 '{module_name}' 依赖 '{dep}' 未启用"
        return True, ""

    def list_modules(self) -> list[dict]:
        result = []
        for name in self.CORE_MODULES + self.OPTIONAL_MODULES:
            result.append({
                "name": name,
                "enabled": self._modules.get(name, True),
                "type": "core" if name in self.CORE_MODULES else "optional",
                "layer": self.get_layer(name),
            })
        return result


module_registry = ModuleRegistry()
