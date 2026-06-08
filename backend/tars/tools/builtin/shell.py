"""Shell 工具 — 黑名单模式，替代旧的白名单 CommandTool"""
import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolResult
from ..sandbox import WorkspaceSandbox


# 敏感系统目录前缀：命令中出现指向这些目录且不在 allowed_dirs 内的绝对路径时拦截。
SENSITIVE_PATH_PREFIXES: List[str] = [
    "/etc", "/var", "/usr", "/root", "/sys", "/proc", "/boot",
    "/bin", "/sbin", "/lib", "/lib64", "/opt", "/dev",
    "/private", "/System", "/Library", "/home", "/Users",
]

# 常见的无害设备路径，允许（如 2>/dev/null）。
SAFE_DEVICE_PATHS = {
    "/dev/null", "/dev/zero", "/dev/stdin", "/dev/stdout",
    "/dev/stderr", "/dev/tty", "/dev/random", "/dev/urandom",
}

# 提取命令中的绝对路径 token（不含 shell 元字符）。
_ABS_PATH_RE = re.compile(r"(?<![\w$])(/[A-Za-z0-9._\-/]+)")


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

    def _validate_command_path_safety(
        self, command: str, allowed_dirs: Optional[List[str]]
    ) -> Optional[str]:
        """拦截访问 workspace 外绝对路径的命令。

        命中敏感系统目录（/etc、/usr、/var、/root 等）且不在 allowed_dirs 内时，
        返回错误描述字符串；安全时返回 None。
        """
        normalized_allowed = []
        for d in (allowed_dirs or []):
            try:
                normalized_allowed.append(str(Path(d).resolve()))
            except Exception:
                continue

        for raw in _ABS_PATH_RE.findall(command):
            # 去掉可能误捕获的尾部标点
            candidate = raw.rstrip(".,;:")
            if candidate in SAFE_DEVICE_PATHS:
                continue
            try:
                resolved = str(Path(candidate).resolve())
            except Exception:
                resolved = candidate

            # 在 allowed_dirs 内 → 放行
            in_allowed = any(
                resolved == base or resolved.startswith(base + "/")
                for base in normalized_allowed
            )
            if in_allowed:
                continue

            # 不在 allowed_dirs 内且命中敏感目录 → 拦截
            for prefix in SENSITIVE_PATH_PREFIXES:
                if candidate == prefix or candidate.startswith(prefix + "/") \
                        or resolved == prefix or resolved.startswith(prefix + "/"):
                    return (
                        f"命令访问了 workspace 外的受保护路径: {candidate}"
                    )
        return None

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "").strip()
        cwd = kwargs.get("cwd", "")
        timeout = kwargs.get("timeout", 60)
        allowed_dirs = kwargs.get("_allowed_dirs")
        _workspace_dir = kwargs.get("_workspace_dir")

        if not command:
            return ToolResult(success=False, output="", error="请提供命令")

        if self._is_forbidden(command):
            return ToolResult(success=False, output="", error="命令被禁止（超高危操作）")

        # 绝对路径安全校验：默认仅允许 workspace / tmp / 显式 allowed_dirs。
        effective_allowed = list(allowed_dirs) if allowed_dirs else []
        if _workspace_dir and _workspace_dir not in effective_allowed:
            effective_allowed.append(_workspace_dir)
        _tmp_dir = kwargs.get("_tmp_dir")
        if _tmp_dir and _tmp_dir not in effective_allowed:
            effective_allowed.append(_tmp_dir)
        path_error = self._validate_command_path_safety(command, effective_allowed)
        if path_error:
            return ToolResult(success=False, output="", error=path_error)

        if self._needs_confirmation(command):
            return ToolResult(
                success=False,
                output="",
                error="删除操作需要用户确认",
                metadata={"needs_confirmation": True, "command": command},
            )

        # 解析工作目录
        try:
            _workspace_dir = kwargs.get("_workspace_dir")
            if _workspace_dir:
                from ..sandbox import WorkspaceSandbox
                sandbox = WorkspaceSandbox(workspace_dir=_workspace_dir)
            else:
                sandbox = self.sandbox
            work_dir = str(sandbox.resolve(cwd)) if cwd else sandbox.workspace_path
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
