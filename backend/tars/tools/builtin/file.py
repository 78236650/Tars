"""文件操作工具 - 合并读取和目录列表"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolResult


class FileTool(BaseTool):
    name: str = "file"
    description: str = "读取本地文件内容，支持指定行范围。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "encoding": {"type": "string", "description": "编码，默认 utf-8"},
            "start_line": {"type": "integer", "description": "起始行号（从1开始），可选"},
            "end_line": {"type": "integer", "description": "结束行号，可选"},
        },
        "required": ["path"],
    }

    def __init__(self, allowed_dirs: Optional[List[str]] = None):
        self.allowed_dirs = allowed_dirs or []

    def _is_path_allowed(self, path: Path) -> bool:
        if not self.allowed_dirs:
            return True
        resolved = str(path.resolve())
        return any(resolved.startswith(str(Path(d).resolve())) for d in self.allowed_dirs)

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("path", "")
        encoding = kwargs.get("encoding", "utf-8")
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        if not file_path:
            return ToolResult(success=False, output="", error="请提供文件路径")

        path = Path(file_path).resolve()

        if not path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"路径不是文件: {file_path}")
        if not self._is_path_allowed(path):
            return ToolResult(success=False, output="", error=f"路径不在允许目录内: {file_path}")

        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()

            if start_line or end_line:
                s = (start_line or 1) - 1
                e = end_line or len(lines)
                lines = lines[s:e]

            content = "".join(lines)
            if len(content) > 50000:
                content = content[:50000] + "\n... (内容过长已截断)"

            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(path), "total_lines": len(lines)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取文件失败: {e}")


class FileListTool(BaseTool):
    name: str = "file_list"
    description: str = "列出目录中的文件和子目录。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认当前目录"},
            "pattern": {"type": "string", "description": "文件过滤模式（如 *.py）"},
            "recursive": {"type": "boolean", "description": "是否递归列出"},
        },
        "required": [],
    }

    async def execute(self, **kwargs) -> ToolResult:
        dir_path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern")
        recursive = kwargs.get("recursive", False)

        target = Path(dir_path).resolve()
        if not target.exists():
            return ToolResult(success=False, output="", error=f"路径不存在: {dir_path}")
        if not target.is_dir():
            return ToolResult(success=False, output="", error=f"路径不是目录: {dir_path}")

        try:
            if recursive:
                items = list(target.rglob(pattern or "*"))
            elif pattern:
                items = list(target.glob(pattern))
            else:
                items = list(target.iterdir())

            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            dirs = [i for i in items if i.is_dir()]
            files = [i for i in items if i.is_file()]

            lines = [f"目录: {target}", f"共 {len(dirs)} 个目录, {len(files)} 个文件", ""]
            for d in dirs[:30]:
                lines.append(f"  [DIR] {d.name}/")
            for f in files[:50]:
                size = f.stat().st_size
                lines.append(f"  {f.name} ({self._fmt_size(size)})")
            if len(files) > 50:
                lines.append(f"  ... 还有 {len(files) - 50} 个文件")

            return ToolResult(success=True, output="\n".join(lines), metadata={"total": len(items)})
        except Exception as e:
            return ToolResult(success=False, output="", error=f"列出目录失败: {e}")

    @staticmethod
    def _fmt_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
