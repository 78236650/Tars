"""Shell 工具 — 黑名单模式，替代旧的白名单 CommandTool"""
import asyncio
import re
from typing import Any, Dict, List

from ..base import BaseTool, ToolResult
from ..sandbox import WorkspaceSandbox


FORBIDDEN_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\$HOME",
    r":\(\)\{",                 # fork bomb
    r">\s*/etc/",
    r">\s*/var/",
    r">\s*/usr/",
    r"curl\s+.*\|\s*(ba)?sh",
    r"wget\s+.*\|\s*(ba)?sh",
    r"sudo\s+rm\s+-rf",
    r"mkfs\.",
    r"dd\s+if=.*/dev/",
    r"nc\s+-[^ ]*e",
    r"bash\s+-i\s+>&",
]

DELETE_PATTERNS: List[str] = [
    r"\brm\b",
    r"\bunlink\b",
    r"\brmdir\b",
    r"shutil\.rmtree",
]


class ShellTool(BaseTool):
    name: str = "shell"
    description: str = "在 workspace 内执行 shell 命令。大部分命令可直接执行，仅禁止超高危操作。删除操作需要确认。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "cwd": {"type": "string", "description": "工作目录（相对 workspace），默认 workspace 根目录"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 60"},
        },
        "required": ["command"],
    }

    def __init__(self, sandbox: WorkspaceSandbox):
        self.sandbox = sandbox

    def _is_forbidden(self, command: str) -> bool:
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def _needs_confirmation(self, command: str) -> bool:
        for pattern in DELETE_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "").strip()
        cwd = kwargs.get("cwd", "")
        timeout = kwargs.get("timeout", 60)

        if not command:
            return ToolResult(success=False, output="", error="请提供命令")

        if self._is_forbidden(command):
            return ToolResult(success=False, output="", error="命令被禁止（超高危操作）")

        if self._needs_confirmation(command):
            return ToolResult(
                success=False,
                output="",
                error="删除操作需要用户确认",
                metadata={"needs_confirmation": True, "command": command},
            )

        # 解析工作目录
        try:
            work_dir = str(self.sandbox.resolve(cwd)) if cwd else self.sandbox.workspace_path
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                full_output = output
                if err_output:
                    full_output += f"\n[stderr]\n{err_output}"
                return ToolResult(
                    success=True,
                    output=full_output or "(命令执行成功)",
                    metadata={"returncode": 0, "cwd": work_dir},
                )
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=err_output or f"退出码: {proc.returncode}",
                    metadata={"returncode": proc.returncode, "cwd": work_dir},
                )
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error=f"命令超时（{timeout}秒）")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"执行失败: {e}")
