"""Tenant-scoped skill directory layout — v4.1.0"""
from pathlib import Path
from typing import List, Optional


GLOBAL_DIR = "_global"
TENANTS_DIR = "tenants"
RESERVED = {GLOBAL_DIR, TENANTS_DIR}


class TenantSkillPaths:
    """skills/_global + skills/tenants/{tenant_id}/"""

    def __init__(self, skills_root: str):
        self.skills_root = Path(skills_root).resolve()
        self.skills_root.mkdir(parents=True, exist_ok=True)
        (self.skills_root / TENANTS_DIR).mkdir(exist_ok=True)

    @property
    def uses_v41_layout(self) -> bool:
        return (self.skills_root / GLOBAL_DIR).is_dir()

    @property
    def global_dir(self) -> Path:
        d = self.skills_root / GLOBAL_DIR
        d.mkdir(exist_ok=True)
        return d

    def tenant_dir(self, tenant_id: str) -> Path:
        self._validate_tenant_id(tenant_id)
        d = self.skills_root / TENANTS_DIR / tenant_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load_dirs(self, tenant_id: Optional[str] = None) -> List[Path]:
        """Directories to scan for skills."""
        if not self.uses_v41_layout:
            return [self.skills_root]

        dirs = [self.global_dir]
        if tenant_id:
            tdir = self.skills_root / TENANTS_DIR / tenant_id
            if tdir.is_dir():
                dirs.append(tdir)
        else:
            tenants_root = self.skills_root / TENANTS_DIR
            if tenants_root.is_dir():
                for item in sorted(tenants_root.iterdir()):
                    if item.is_dir() and not item.name.startswith("."):
                        dirs.append(item)
        return dirs

    def install_target(self, skill_id: str, scope: str, tenant_id: str = "default") -> Path:
        safe_id = skill_id.replace("/", "-").replace(" ", "-")
        if scope == "global":
            return self.global_dir / safe_id
        self._validate_tenant_id(tenant_id)
        return self.tenant_dir(tenant_id) / safe_id

    @staticmethod
    def _validate_tenant_id(tenant_id: str) -> None:
        if not tenant_id or ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
            raise ValueError(f"非法 tenant_id: {tenant_id}")

    def migrate_flat_to_global(self) -> int:
        """Move legacy flat skills/* into skills/_global/*. Idempotent."""
        if self.uses_v41_layout:
            return 0

        global_dir = self.skills_root / GLOBAL_DIR
        global_dir.mkdir(exist_ok=True)
        moved = 0

        for item in list(self.skills_root.iterdir()):
            if not item.is_dir() or item.name.startswith(".") or item.name in RESERVED:
                continue
            if not ((item / "skill.yaml").exists() or (item / "SKILL.md").exists()):
                continue
            target = global_dir / item.name
            if target.exists():
                continue
            item.rename(target)
            moved += 1

        return moved
