"""Python 代码执行工具 — 沙箱化运行 Python 脚本"""
import asyncio
import os
import sys
import tempfile
from typing import Any, Dict, List

from ..base import BaseTool, ToolResult


# 注入到用户代码前的安全前导：覆写 open 校验绝对路径、拦截危险调用。
_GUARD_PREAMBLE = '''# -*- coding: utf-8 -*-
import builtins as _b
import os as _os

_ALLOWED_DIRS = {allowed_dirs!r}


def _path_allowed(_p):
    try:
        _rp = _os.path.realpath(_os.fspath(_p))
    except Exception:
        return True
    if not _os.path.isabs(str(_p)):
        return True
    for _base in _ALLOWED_DIRS:
        try:
            _rbase = _os.path.realpath(_base)
        except Exception:
            continue
        if _rp == _rbase or _rp.startswith(_rbase + _os.sep):
            return True
    return False


_orig_open = _b.open


def _guarded_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, _os.PathLike)) and not _path_allowed(file):
        raise PermissionError(
            "禁止访问 workspace 外的绝对路径: %s" % (file,)
        )
    return _orig_open(file, mode, *args, **kwargs)


_b.open = _guarded_open

# 拦截可绕过 open 守卫的进程级调用
def _blocked(*_a, **_k):
    raise PermissionError("沙箱内禁止调用该函数（可能绕过路径限制）")


_os.system = _blocked
if hasattr(_os, "popen"):
    _os.popen = _blocked

# 危险 import 告警
_orig_import = _b.__import__


def _guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in ("subprocess",):
        import sys as _sys
        print(
            "[sandbox warning] 已 import %s，注意：绕过沙箱路径限制的操作会被拒绝" % name,
            file=_sys.stderr,
        )
    return _orig_import(name, *args, **kwargs)


_b.__import__ = _guarded_import
# ===== 用户代码开始 =====
'''



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
        _workspace_dir = kwargs.get("_workspace_dir", self.workspace_dir)
        _tmp_dir = kwargs.get("_tmp_dir", _workspace_dir)
        _allowed_dirs = kwargs.get("_allowed_dirs")

        if not code:
            return ToolResult(success=False, output="", error="请提供 Python 代码")

        # 计算受限的 allowed_dirs：默认 workspace + tmp + 显式 allowed_dirs。
        allowed: List[str] = []
        for d in (_allowed_dirs or []):
            if d:
                allowed.append(str(d))
        for d in (_workspace_dir, _tmp_dir):
            if d and str(d) not in allowed:
                allowed.append(str(d))

        guarded_code = _GUARD_PREAMBLE.format(allowed_dirs=allowed) + "\n" + code

        # 写临时文件避免 shell 转义
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=_tmp_dir, encoding="utf-8"
        ) as f:
            f.write(guarded_code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=_workspace_dir,
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
