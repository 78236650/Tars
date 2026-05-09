"""变量替换引擎 — v2.5 workspace 变量 + 按需 shlex.quote

支持变量：
- {{workspace.path}}    — 工作区路径
- {{workspace.pm}}      — 包管理器 (npm/pnpm/yarn/pip)
- {{workspace.branch}}  — git 当前分支
- {{step_N.output}}     — 前序步骤输出（保留原样给 executor._resolve_placeholders 处理）
- {{env.HOME}}          — 白名单环境变量

安全策略：
- 仅在 shell 参数上启用 shlex.quote（防命令注入）
- 非 shell 参数（如 file_write.path）保留原始值
- {{step_N.*}} 原样保留，让 executor 在运行时用真实步骤结果替换
"""
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict

# 环境变量白名单
SAFE_ENV_VARS = {"HOME", "USER", "PATH", "SHELL", "LANG", "PWD"}

# 按 tool name 决定哪些参数要 shlex.quote
SHELL_QUOTE_PARAMS: Dict[str, set] = {
    "shell": {"cmd", "command"},
    "bash": {"cmd", "command"},
}


class VariableEngine:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self._pm = None
        self._branch = None

    @property
    def package_manager(self) -> str:
        if self._pm is None:
            self._pm = self._detect_pm()
        return self._pm

    @property
    def branch(self) -> str:
        if self._branch is None:
            self._branch = self._detect_branch()
        return self._branch

    def resolve(self, text: str, quote_for_shell: bool = False) -> str:
        """替换文本中的 {{workspace.*}} / {{env.*}} 变量。

        {{step_N.*}} 保留原样，让 executor 后续替换。
        quote_for_shell=True 时对注入值做 shlex.quote。
        """
        if not text or "{{" not in text:
            return text

        def replacer(match):
            var = match.group(1).strip()
            # step_N.* 保留原样
            if var.startswith("step_"):
                return match.group(0)
            value = self._lookup(var)
            if value is None:
                return match.group(0)  # 未识别的变量原样保留
            value = str(value)
            return shlex.quote(value) if quote_for_shell else value

        return re.sub(r'\{\{(.*?)\}\}', replacer, text)

    def resolve_dict(self, data: Any, tool_name: str = "") -> Any:
        """递归替换 dict/list。按 tool_name 判断是否需要 shlex.quote。

        在 agent.py 里对每个 step 调用时，传入 step.tool 即可。
        """
        quote_params = SHELL_QUOTE_PARAMS.get(tool_name, set())

        def _walk(value: Any, parent_key: str = "") -> Any:
            if isinstance(value, str):
                is_shell_param = parent_key in quote_params
                return self.resolve(value, quote_for_shell=is_shell_param)
            if isinstance(value, dict):
                return {k: _walk(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [_walk(v, parent_key) for v in value]
            return value

        return _walk(data)

    def _lookup(self, var: str):
        if var == "workspace.path":
            return self.workspace_path
        if var == "workspace.pm":
            return self.package_manager
        if var == "workspace.branch":
            return self.branch
        if var.startswith("env."):
            env_key = var[4:]
            if env_key in SAFE_ENV_VARS:
                return os.environ.get(env_key, "")
            return ""  # 非白名单环境变量返回空串
        return None  # 未识别

    def _detect_pm(self) -> str:
        root = Path(self.workspace_path)
        checks = [
            ("pnpm", "pnpm-lock.yaml"), ("yarn", "yarn.lock"),
            ("npm", "package-lock.json"), ("npm", "package.json"),
            ("poetry", "poetry.lock"), ("poetry", "pyproject.toml"),
            ("pip", "requirements.txt"),
        ]
        for pm, file in checks:
            if (root / file).exists():
                return pm
        return "npm"

    def _detect_branch(self) -> str:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_path, capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip() or "main"
        except Exception:
            return "main"
