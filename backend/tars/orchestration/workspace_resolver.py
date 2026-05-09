"""Workspace 路径解析 — v2.4 四级优先级"""
import os
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import Optional, Tuple


def resolve_workspace_path(
    session_id: str,
    api_override: Optional[str] = None,
    title: str = "unnamed_task",
) -> Tuple[str, str]:
    """返回 (workspace_path, source)。

    source 取值: api / workspace_manager / tars_repo_root / tars_fallback
    """
    # 1. API 显式传入
    if api_override and Path(api_override).exists():
        return api_override, "api"

    # 2. Workspace Manager（若接口已实现）
    try:
        from tars.workspace import WorkspaceManager
        wm = WorkspaceManager()
        ws = getattr(wm, "get_session_workspace", lambda _: None)(session_id)
        if ws:
            return ws, "workspace_manager"
    except Exception:
        pass

    # 3. TARS 仓库根目录兜底（backend/..）
    project_root = Path(__file__).resolve().parent.parent.parent
    if project_root.exists() and (project_root / ".git").exists():
        return str(project_root), "tars_repo_root"

    # 4. ~/.tars/workspaces/{slug}/
    slug = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + _title_to_slug(title)
    path = Path.home() / ".tars" / "workspaces" / slug
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        run(["git", "init"], cwd=path, capture_output=True)
    return str(path), "tars_fallback"


def detect_workspace_context(workspace_path: str) -> dict:
    """检测工作区上下文，返回可用操作列表"""
    path = Path(workspace_path)
    context = {
        "workspace_path": str(path),
        "has_git": (path / ".git").exists(),
        "has_remote": False,
        "build_tools": [],
        "available_ops": [],
    }

    if context["has_git"]:
        context["available_ops"].extend(["add", "commit", "status", "log", "diff"])
        try:
            from subprocess import run
            result = run(["git", "remote"], cwd=path, capture_output=True, text=True)
            if result.stdout.strip():
                context["has_remote"] = True
                context["available_ops"].extend(["push", "pull", "fetch"])
        except Exception:
            pass

    # 检测构建工具
    for tool, files in [
        ("npm", ["package.json"]),
        ("pnpm", ["pnpm-lock.yaml"]),
        ("yarn", ["yarn.lock"]),
        ("pip", ["requirements.txt"]),
        ("poetry", ["pyproject.toml"]),
    ]:
        if any((path / f).exists() for f in files):
            context["build_tools"].append(tool)
            context["available_ops"].append(f"{tool}_install")

    return context


def _title_to_slug(title: str) -> str:
    """中文标题转英文 slug（简易版：取前 20 个非中文字符）"""
    import re
    slug = re.sub(r'[^\w\s-]', '', title)
    slug = re.sub(r'[\u4e00-\u9fff]', '', slug)  # 去掉中文
    slug = re.sub(r'\s+', '_', slug.strip())[:40]
    return slug or "task"

