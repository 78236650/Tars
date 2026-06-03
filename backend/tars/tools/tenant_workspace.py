"""Per-tenant workspace 隔离 — v4.0.1.

每个租户拥有独立的文件目录，防止跨租户文件访问。
"""
from pathlib import Path
from .sandbox import WorkspaceSandbox


class TenantWorkspaceManager:
    def __init__(self, base_dir: str = "~/.tars/workspaces", extra_allowed_dirs: list[str] = None):
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "_shared").mkdir(exist_ok=True)
        self._extra_dirs = [str(Path(d).resolve()) for d in (extra_allowed_dirs or []) if Path(d).exists()]

    def get_workspace(self, tenant_id: str) -> Path:
        self._validate(tenant_id)
        ws = self.base_dir / tenant_id / "files"
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def get_tmp_dir(self, tenant_id: str) -> Path:
        self._validate(tenant_id)
        tmp = self.base_dir / tenant_id / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp

    def get_sandbox(self, tenant_id: str) -> WorkspaceSandbox:
        return WorkspaceSandbox(workspace_dir=str(self.get_workspace(tenant_id)))

    def get_allowed_dirs(self, tenant_id: str, role: str = "user") -> list[str]:
        dirs = [str(self.get_workspace(tenant_id)), str(self.base_dir / "_shared")]
        if role == "admin":
            dirs.append(str(self.base_dir))
        dirs.extend(self._extra_dirs)
        return dirs

    def _validate(self, tenant_id: str):
        if not tenant_id or ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
            raise ValueError(f"非法 tenant_id: {tenant_id}")


# 全局单例（main.py 启动时初始化）
tenant_workspace_manager: TenantWorkspaceManager | None = None


def init_tenant_workspace(base_dir: str = "~/.tars/workspaces", extra_allowed_dirs: list[str] = None) -> TenantWorkspaceManager:
    global tenant_workspace_manager
    tenant_workspace_manager = TenantWorkspaceManager(base_dir, extra_allowed_dirs=extra_allowed_dirs)
    return tenant_workspace_manager
