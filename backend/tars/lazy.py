"""Lazy import utility — v4.0.0 Phase 2.

Delays heavy module imports until first actual use,
significantly reducing cold-start time.
"""
import importlib
from typing import Any


class LazyModule:
    """Proxy that imports the real module only when accessed."""

    def __init__(self, module_path: str):
        self._module_path = module_path
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_path)
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)


def lazy_import(module_path: str) -> LazyModule:
    """Return a lazy proxy for *module_path*."""
    return LazyModule(module_path)
