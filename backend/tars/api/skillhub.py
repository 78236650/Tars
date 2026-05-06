"""TARS API - SkillHub 商店路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/skillhub", tags=["SkillHub 商店"])

# 全局引用，在 app 初始化时设置
_client = None
_installer = None


def init_skillhub_api(client, installer):
    global _client, _installer
    _client = client
    _installer = installer


class InstallRequest(BaseModel):
    skill_id: str
    confirm_permissions: bool = True


class UninstallRequest(BaseModel):
    skill_id: str


@router.get("/search")
async def search_skills(q: str = ""):
    """搜索 SkillHub 技能"""
    if not _client:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    results = await _client.search(q)
    return {
        "success": True,
        "query": q,
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.get("/detail/{skill_id:path}")
async def get_skill_detail(skill_id: str):
    """获取技能包详情"""
    if not _client:
        raise HTTPException(status_code=503, detail="SkillHub 未初始化")

    pkg = await _client.get_detail(skill_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")
    return {"success": True, "package": pkg.to_dict()}


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
