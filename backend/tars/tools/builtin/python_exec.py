"""Python 代码执行工具 — 沙箱化运行 Python 脚本"""
import asyncio
import os
import sys
import tempfile
from typing import Any, Dict

from ..base import BaseTool, ToolResult


class PythonExecTool(BaseTool):
    name: str = "python_exec"
    description: str = (
        "在沙箱子进程中执行 Python 代码，返回 stdout、stderr 和退出码。\n"
        "用于：数据分析（CSV/Excel/JSON）、文件格式转换、快速原型验证、\n"
        "数据处理（pandas/numpy）、图片处理（Pillow）、PDF 读取等任何需要写代码的任务。\n"
        "代码在当前工作区目录下执行，可访问所有项目文件。\n"
        "⚠️ 使用 print() 输出结果；不支持 async/await；子进程隔离执行。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python 代码。使用 print() 输出结果。可 import pandas,numpy,json,csv,PIL 等。",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30",
                "default": 30,
            },
        },
        "required": ["code"],
    }

    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or os.getcwd()

    async def execute(self, **kwargs) -> ToolResult:
        code = kwargs.get("code", "").strip()
        timeout = kwargs.get("timeout", 30)

        if not code:
            return ToolResult(success=False, output="", error="请提供 Python 代码")

        # 写临时文件避免 shell 转义
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=self.workspace_dir, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            parts = []
            if out_text:
                parts.append(out_text)
            if err_text:
                parts.append(f"[stderr]\n{err_text}")
            output = "\n".join(parts) if parts else "(无输出)"

            if proc.returncode == 0:
                return ToolResult(success=True, output=output, metadata={"returncode": 0})
            return ToolResult(
                success=False, output=out_text or "(无输出)",
                error=err_text or f"退出码: {proc.returncode}",
                metadata={"returncode": proc.returncode},
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error=f"代码超时（{timeout}秒），检查死循环")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"执行失败: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
