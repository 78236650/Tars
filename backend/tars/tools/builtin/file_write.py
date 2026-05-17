"""文件写入工具 — 在 workspace 内创建/写入/追加/插入内容"""
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import BaseTool, ToolResult
from ..sandbox import WorkspaceSandbox


class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = "在 workspace 内创建或修改文件。支持覆盖写入、追加、指定行插入。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对 workspace 或 workspace 内的绝对路径）"},
            "content": {"type": "string", "description": "要写入的内容"},
            "mode": {
                "type": "string",
                "enum": ["write", "append", "insert"],
                "description": "write(覆盖)/append(追加)/insert(在指定行插入)，默认 write",
            },
            "line": {"type": "integer", "description": "insert 模式时的行号（从1开始）"},
            "create_dirs": {"type": "boolean", "description": "是否自动创建父目录，默认 true"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, sandbox: WorkspaceSandbox):
        self.sandbox = sandbox

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "write")
        line = kwargs.get("line")
        create_dirs = kwargs.get("create_dirs", True)
        _workspace_dir = kwargs.get("_workspace_dir")

        if not path:
            return ToolResult(success=False, output="", error="请提供文件路径")

        # v4.0.1: 优先使用 tenant workspace sandbox
        sandbox = self.sandbox
        if _workspace_dir:
            from ..sandbox import WorkspaceSandbox
            sandbox = WorkspaceSandbox(workspace_dir=_workspace_dir)

        try:
            target = sandbox.resolve(path)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        try:
            if create_dirs:
                target.parent.mkdir(parents=True, exist_ok=True)

            if mode == "write":
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
                action = "写入"
            elif mode == "append":
                with open(target, "a", encoding="utf-8") as f:
                    f.write(content)
                action = "追加到"
            elif mode == "insert":
                if line is None or line < 1:
                    return ToolResult(success=False, output="", error="insert 模式需要有效的 line 参数（>= 1）")
                lines = []
                if target.exists():
                    with open(target, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                insert_idx = min(line - 1, len(lines))
                new_content = content if content.endswith("\n") else content + "\n"
                lines.insert(insert_idx, new_content)
                with open(target, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                action = f"在第{line}行插入到"
            else:
                return ToolResult(success=False, output="", error=f"不支持的 mode: {mode}")

            return ToolResult(
                success=True,
                output=f"已{action} {target}（{len(content)} 字符）",
                metadata={"path": str(target), "size": len(content), "mode": mode},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"文件操作失败: {e}")
