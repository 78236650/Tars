"""变量替换引擎 — v2.5 workspace 变量 + shlex.quote 安全

支持变量：
- {{workspace.path}}    — 工作区路径
- {{workspace.pm}}      — 包管理器 (npm/pnpm/yarn/pip)
- {{workspace.branch}}  — git 当前分支
- {{step_N.output}}     — 前序步骤输出（v2.4 已有）
- {{env.HOME}}          — 白名单环境变量
"""
import os
import re
import shlex
from pathlib import Path
from typing import Dict, Any

# 环境变量白名单
SAFE_ENV_VARS = {"HOME", "USER", "PATH", "SHELL", "LANG", "PWD"}


class VariableEngine:
    """运行时变量替换"""

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

    def resolve(self, text: str, step_results: Dict[int, Any] = None) -> str:
        """替换文本中的所有 {{...}} 变量"""
        if not text or "{{" not in text:
            return text

        def replacer(match):
            var = match.group(1).strip()
            value = self._lookup(var, step_results or {})
            # shlex.quote 防命令注入
            return shlex.quote(str(value))

        return re.sub(r'\{\{(.*?)\}\}', replacer, text)

    def resolve_dict(self, data: Any, step_results: Dict[int, Any] = None) -> Any:
        """递归替换 dict/list 中的所有变量"""
        if isinstance(data, str):
            return self.resolve(data, step_results)
        if isinstance(data, dict):
            return {k: self.resolve_dict(v, step_results) for k, v in data.items()}
        if isinstance(data, list):
            return [self.resolve_dict(v, step_results) for v in data]
        return data

    def _lookup(self, var: str, step_results: dict) -> str:
        var = var.strip()
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
            return ""
        # 兜底：v2.4 {{step_N.output}}
        if var.startswith("step_"):
            return self._resolve_step_ref(var, step_results)
        return f"{{{{{var}}}}}"

    def _resolve_step_ref(self, var: str, results: dict) -> str:
        m = re.match(r'step_(\d+)\.(.+)', var)
        if not m:
            return f"{{{{{var}}}}}"
        step_id = int(m.group(1))
        field = m.group(2)
        result = results.get(step_id)
        if not result:
            return f"{{{{{var}}}}}"
        return getattr(result, field, "") or ""

    def _detect_pm(self) -> str:
        root = Path(self.workspace_path)
        checks = [
            ("pnpm", "pnpm-lock.yaml"), ("yarn", "yarn.lock"),
            ("npm", "package-lock.json"), ("npm", "package.json"),
            ("pip", "requirements.txt"), ("poetry", "pyproject.toml"),
        ]
        for pm, file in checks:
            if (root / file).exists():
                return pm
        return "npm"  # 默认

    def _detect_branch(self) -> str:
        import subprocess
        try:
            r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=self.workspace_path, capture_output=True, text=True)
            return r.stdout.strip() or "main"
        except Exception:
            return "main"
