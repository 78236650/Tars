"""ArtifactsCollector — v2.4 任务产出追踪

两层采集：
1. Planner 预声明：task_steps.expected_artifacts
2. Executor 自动抽取：git status --porcelain + tool 参数提取
"""
import json
import os
from pathlib import Path
from subprocess import run
from typing import List, Optional

# 排除目录（不视为产物）
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".cache"}
EXCLUDE_EXTENSIONS = {".pyc", ".log", ".tmp"}


class ArtifactsCollector:
    """任务产出文件追踪"""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self._snapshot: Optional[set] = None  # 任务开始时的文件快照

    def take_snapshot(self):
        """任务开始前记录文件列表"""
        if not self.workspace_path.exists():
            return
        self._snapshot = set()
        for f in self.workspace_path.rglob("*"):
            if f.is_file() and not self._is_excluded(f):
                self._snapshot.add(str(f.resolve()))

    def collect_new_files(self) -> List[str]:
        """返回任务开始后新增/修改的文件（相对路径）"""
        if self._snapshot is None:
            return self._git_status_files()

        current = set()
        for f in self.workspace_path.rglob("*"):
            if f.is_file() and not self._is_excluded(f):
                current.add(str(f.resolve()))

        new_files = current - self._snapshot
        return [str(Path(f).relative_to(self.workspace_path)) for f in sorted(new_files)]

    @staticmethod
    def collect_from_step(step: dict) -> List[str]:
        """从步骤定义中提取预期产物路径

        step["expected_artifacts"]: ["dist/index.html", ...]
        step["arguments"]: 工具参数（如 file_write 的 path）
        """
        artifacts = []

        # Planner 预声明
        expected = step.get("expected_artifacts", [])
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                expected = []
        artifacts.extend(expected)

        # 从工具参数提取
        args = step.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        for key in ("path", "file", "output", "dest"):
            val = args.get(key)
            if isinstance(val, str) and val:
                artifacts.append(val)

        return list(set(artifacts))

    def _git_status_files(self) -> List[str]:
        """通过 git status 获取变更文件"""
        try:
            result = run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_path, capture_output=True, text=True
            )
            files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # 格式: " M path/to/file" 或 "?? path/to/file"
                    path = line[3:].strip()
                    if path and not self._is_excluded_path(path):
                        files.append(path)
            return files
        except Exception:
            return []

    @staticmethod
    def _is_excluded(file_path: Path) -> bool:
        """判断文件是否应排除"""
        parts = file_path.parts
        for p in parts:
            if p in EXCLUDE_DIRS or p.startswith("."):
                return True
        return file_path.suffix in EXCLUDE_EXTENSIONS

    @staticmethod
    def _is_excluded_path(path_str: str) -> bool:
        parts = Path(path_str).parts
        for p in parts:
            if p in EXCLUDE_DIRS or p.startswith("."):
                return True
        return Path(path_str).suffix in EXCLUDE_EXTENSIONS
