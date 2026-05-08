"""TARS API - SkillHub 商店路由"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/skillhub", tags=["SkillHub 商店"])

# 全局引用，在 app 初始化时设置
_client = None
_installer = None
_skill_registry = None
_catalog_path = None


def init_skillhub_api(client, installer, skill_registry=None, catalog_path: str = None):
    global _client, _installer, _skill_registry, _catalog_path
    _client = client
    _installer = installer
    _skill_registry = skill_registry
    if catalog_path:
        _catalog_path = Path(catalog_path)


class InstallRequest(BaseModel):
    skill_id: str
    confirm_permissions: bool = True


class UninstallRequest(BaseModel):
    skill_id: str


def _get_installed_ids() -> set:
    """获取已安装的技能 ID 集合"""
    ids = set()
    if _installer:
        ids.update(_installer.list_installed())
    if _skill_registry:
        ids.update(s.id for s in _skill_registry.list_all())
    return ids


def _normalize_id(s: str) -> str:
    """归一化技能 ID：统一连字符/下划线，便于跨来源匹配"""
    return s.replace("-", "_").replace(" ", "_").lower()


def _annotate_installed(packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为包列表标注 installed 状态"""
    installed_ids = _get_installed_ids()
    normalized_installed = {_normalize_id(sid) for sid in installed_ids}
    for pkg in packages:
        pkg_id = pkg.get("id", "")
        pkg_name = pkg_id.split("/")[-1] if "/" in pkg_id else pkg_id
        pkg["installed"] = (
            pkg_id in installed_ids
            or _normalize_id(pkg_id) in normalized_installed
            or _normalize_id(pkg_name) in normalized_installed
        )
    return packages


def _load_catalog() -> List[Dict[str, Any]]:
    """加载本地技能目录"""
    if not _catalog_path or not _catalog_path.exists():
        return []
    try:
        with open(_catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[SkillHub] 加载目录失败: {e}")
        return []


@router.get("/catalog")
async def get_catalog():
    """获取本地技能目录（已标注安装状态）"""
    packages = _load_catalog()
    return {
        "success": True,
        "count": len(packages),
        "results": _annotate_installed(packages),
    }


@router.get("/search")
async def search_skills(q: str = ""):
    """搜索 SkillHub 技能（先查本地目录，再查 GitHub）"""
    if not _client:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    # 1. 先查本地目录
    catalog = _load_catalog()
    local_results = []
    if q:
        q_lower = q.lower()
        for pkg in catalog:
            name = pkg.get("name", "").lower()
            desc = pkg.get("description", "").lower()
            tags = " ".join(pkg.get("tags", [])).lower()
            if q_lower in name or q_lower in desc or q_lower in tags:
                local_results.append(pkg)
    else:
        local_results = catalog

    # 2. 本地结果标注已安装状态
    results = _annotate_installed(local_results)

    # 3. 如果本地不够，补充 GitHub 搜索
    if not results:
        github_results = await _client.search(q)
        results = _annotate_installed([r.to_dict() for r in github_results])

    return {
        "success": True,
        "query": q,
        "count": len(results),
        "results": results,
    }


@router.get("/detail/{skill_id:path}")
async def get_skill_detail(skill_id: str):
    """获取技能包详情（先查本地目录，再查 GitHub）"""
    # 先查本地目录
    catalog = _load_catalog()
    for pkg in catalog:
        if pkg.get("id") == skill_id:
            installed_ids = _get_installed_ids()
            pkg_name = skill_id.split("/")[-1] if "/" in skill_id else skill_id
            pkg["installed"] = skill_id in installed_ids or pkg_name in installed_ids
            return {"success": True, "package": pkg}

    # 再查 GitHub
    if not _client:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    pkg = await _client.get_detail(skill_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")
    result = pkg.to_dict()
    installed_ids = _get_installed_ids()
    result["installed"] = skill_id in installed_ids
    return {"success": True, "package": result}


@router.post("/install")
async def install_skill(request: InstallRequest):
    """安装技能"""
    if not _installer:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    result = await _installer.install(request.skill_id, confirm_permissions=request.confirm_permissions)
    if result.get("success"):
        return result
    if result.get("needs_confirmation"):
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "安装失败"))


@router.post("/uninstall")
async def uninstall_skill(request: UninstallRequest):
    """卸载技能"""
    if not _installer:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    result = _installer.uninstall(request.skill_id)
    if result.get("success"):
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "卸载失败"))


@router.get("/installed")
async def list_installed():
    """列出已安装的 SkillHub 技能"""
    if not _installer:
        return {"skills": [], "count": 0}

    installed = _installer.list_installed()
    return {"success": True, "skills": installed, "count": len(installed)}


@router.get("/updates")
async def check_updates():
    """检查更新"""
    if not _installer:
        return {"updates": []}

    installed = _installer.list_installed()
    updates = await _installer.check_updates(installed)
    return {"success": True, "updates": updates}
