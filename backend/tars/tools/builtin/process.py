"""进程管理工具"""
import asyncio
import os
import signal
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolResult


class ProcessTool(BaseTool):
    name: str = "process"
    description: str = "管理进程：列出运行中的进程、启动后台进程、终止进程、查询状态"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "start", "stop", "status"],
                "description": "操作类型",
            },
            "command": {"type": "string", "description": "start 时的命令"},
            "pid": {"type": "integer", "description": "stop/status 时的进程 ID"},
            "name": {"type": "string", "description": "按名称过滤（list 时可用）"},
            "cwd": {"type": "string", "description": "start 时的工作目录"},
        },
        "required": ["action"],
    }

    def __init__(self):
        self._managed: Dict[int, Dict] = {}

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "list":
            return await self._list_processes(kwargs.get("name"))
        if action == "start":
            return await self._start(kwargs.get("command"), kwargs.get("cwd"))
        if action == "stop":
            return await self._stop(kwargs.get("pid"))
        if action == "status":
            return await self._status(kwargs.get("pid"))

        return ToolResult(success=False, output="", error=f"未知操作: {action}")

    async def _list_processes(self, name_filter: Optional[str] = None) -> ToolResult:
        try:
            output = await self._run_ps_command("ps aux")
            if not output.strip():
                output = await self._run_ps_command("ps -A -o pid=,comm=")

            if name_filter:
                lines = output.split("\n")
                filtered = [lines[0]] if lines else []
                filtered.extend(l for l in lines[1:] if name_filter.lower() in l.lower())
                output = "\n".join(filtered[:30])
            else:
                output = "\n".join(output.split("\n")[:30])

            if not output.strip():
                return ToolResult(
                    success=True,
                    output="USER       PID  COMMAND\n(当前环境无法列出进程，可能受沙箱限制)",
                )
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"列出进程失败: {e}")

    async def _run_ps_command(self, command: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return stdout.decode("utf-8", errors="replace")

    async def _start(self, command: Optional[str], cwd: Optional[str]) -> ToolResult:
        if not command:
            return ToolResult(success=False, output="", error="start 需要 command")
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                start_new_session=True,
            )
            self._managed[proc.pid] = {"command": command, "process": proc}
            return ToolResult(
                success=True,
                output=f"进程已启动，PID: {proc.pid}",
                metadata={"pid": proc.pid, "command": command},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"启动失败: {e}")

    async def _stop(self, pid: Optional[int]) -> ToolResult:
        if not pid:
            return ToolResult(success=False, output="", error="stop 需要 pid")
        try:
            os.kill(pid, signal.SIGTERM)
            self._managed.pop(pid, None)
            return ToolResult(success=True, output=f"已发送 SIGTERM 给 PID {pid}")
        except ProcessLookupError:
            return ToolResult(success=False, output="", error=f"进程 {pid} 不存在")
        except PermissionError:
            return ToolResult(success=False, output="", error=f"无权限终止 PID {pid}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"终止失败: {e}")

    async def _status(self, pid: Optional[int]) -> ToolResult:
        if not pid:
            return ToolResult(success=False, output="", error="status 需要 pid")
        try:
            os.kill(pid, 0)  # signal 0 测试进程存在
            return ToolResult(success=True, output=f"PID {pid} 运行中")
        except ProcessLookupError:
            return ToolResult(success=True, output=f"PID {pid} 不存在")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"查询失败: {e}")
