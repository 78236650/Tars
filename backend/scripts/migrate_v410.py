#!/usr/bin/env python3
"""Migrate skills/ flat layout → skills/_global/ + skills/tenants/ (v4.1.0)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tars.skills.tenant_paths import TenantSkillPaths  # noqa: E402


def main() -> int:
    skills_root = ROOT / "skills"
    paths = TenantSkillPaths(str(skills_root))
    moved = paths.migrate_flat_to_global()
    print(f"[migrate_v410] skills root: {skills_root}")
    print(f"[migrate_v410] moved {moved} skill(s) to _global/")
    print(f"[migrate_v410] layout v4.1: {paths.uses_v41_layout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
