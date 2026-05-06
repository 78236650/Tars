"""Workspace 沙箱 — 限制所有文件操作在 workspace 目录内"""
from pathlib import Path


class WorkspaceSandbox:
    """路径安全沙箱"""

    def __init__(self, workspace_dir: str):
        self.root = Path(workspace_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str) -> Path:
        """解析路径，确保不逃逸出 workspace。返回绝对路径。"""
        if not path:
            return self.root

        # 处理绝对路径：如果在 workspace 内则允许
        p = Path(path)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (self.root / path).resolve()

        if not str(resolved).startswith(str(self.root)):
            raise PermissionError(f"路径超出 workspace: {path} (resolved: {resolved})")

        return resolved

    def is_within(self, path: str) -> bool:
        """检查路径是否在 workspace 内"""
        try:
            self.resolve(path)
            return True
        except PermissionError:
            return False

    @property
    def workspace_path(self) -> str:
        return str(self.root)
