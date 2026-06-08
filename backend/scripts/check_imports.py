#!/usr/bin/env python
"""Pre-deploy guard: import every API module so dangling imports fail fast.

The standalone ``knowledge`` package was removed in v5.0.4/v5.0.5; lazy imports
to deleted modules don't fail at startup, only when a code path is hit. This
script forces every ``tars.api.*`` module to import so such breakage surfaces
in CI instead of in production.

Exit 0 = all imports OK; exit 1 = at least one failed (details on stderr).
"""
from __future__ import annotations

import importlib
import pkgutil
import sys

import tars.api as api_pkg


def main() -> int:
    failures: list[tuple[str, str]] = []
    for mod in pkgutil.iter_modules(api_pkg.__path__):
        name = f"tars.api.{mod.name}"
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report every failure
            failures.append((name, f"{type(exc).__name__}: {exc}"))

    if failures:
        print("Import check FAILED:", file=sys.stderr)
        for name, err in failures:
            print(f"  - {name}: {err}", file=sys.stderr)
        return 1

    print("Import check OK: all tars.api.* modules import cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
