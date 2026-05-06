"""命令执行工具 - 带白名单保护"""
import asyncio
import re
import subprocess
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolResult


COMMAND_WHITELIST: List[str] = [
    "git", "ls", "ll", "pwd", "cat", "head", "tail", "grep", "find",
    "wc", "sort", "uniq", "cut", "diff", "echo",
    "uname", "whoami", "date", "uptime", "df", "du", "ps",
    "python", "python3", "pip", "pip3", "node", "npm", "yarn",
    "docker ps", "docker images", "docker logs",
    "curl", "wget",
]

FORBIDDEN_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/", r"rm\s+-rf\s+\*",
    r":\(\)\{", r"eval\s+\$\(", r"exec\s+",
    r"sudo\s+su", r"chmod\s+777",
    r">\s*/etc/", r">\s*/var/",
    r"curl\s+.*\|\s*sh", r"wget.*\|\s*sh",
    r"nc\s+-[^ ]*e", r"bash\s+-i",
]


class CommandTool(BaseTool):
    name: str = "command"
    description: str = "在本地系统执行命令。支持白名单内的常用命令（git、ls、python 等），危险命令被禁止。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"},
            "cwd": {"type": "string", "description": "工作目录，默认当前目录"},
            "timeout": {"type": "integer", "description": "超时秒数，默认30"},
        },
        "required": ["command"],
    }

    def __init__(self, whitelist: Optional[List[str]] = None):
        self.whitelist = set(whitelist or COMMAND_WHITELIST)

    def _is_allowed(self, command: str) -> bool:
        cmd = command.strip()
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return False
        for allowed in self.whitelist:
            if cmd == allowed or cmd.startswith(allowed + " "):
                return True
        return False

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd", None)
        timeout = kwargs.get("timeout", 30)

        if not command:
            return ToolResult(success=False, output="", error="请提供命令")

        if not self._is_allowed(command):
            return ToolResult(success=False, output="", error=f"命令不在白名单内或包含危险操作")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return ToolResult(
                    success=True,
                    output=output or "(命令执行成功，无输出)",
                    metadata={"returncode": proc.returncode},
                )
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=err_output or f"退出码: {proc.returncode}",
                    metadata={"returncode": proc.returncode},
                )
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error=f"命令超时（{timeout}秒）")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"命令执行失败: {e}")
