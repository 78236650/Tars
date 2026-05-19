"""TARS API - 技能管理路由"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..skills import skill_registry, SkillType

router = APIRouter(prefix="/api/skills", tags=["技能管理"])

_skill_loader = None
_tool_registry = None


def init_skills_api(skill_loader=None, tool_registry=None):
    global _skill_loader, _tool_registry
    _skill_loader = skill_loader
    _tool_registry = tool_registry


class CreatePromptSkillRequest(BaseModel):
    id: str
    name: str
    description: str
    prompt_template: str
    tags: List[str] = []
    parameters: List[Dict[str, Any]] = []


@router.get("/")
async def list_skills(x_tenant_id: Optional[str] = Header(default="default")):
    """列出当前 tenant 可见的已安装技能"""
    tenant_id = x_tenant_id or "default"
    skills = skill_registry.list_for_tenant(tenant_id)
    return {
        "skills": [s.to_dict() for s in skills],
        "total": len(skills),
        "tenant_id": tenant_id,
    }


# ── v4.0.0: Skill Curator API (before /{skill_id} to avoid route conflict) ──

@router.get("/stats")
async def get_skill_stats():
    """Get usage stats for all tracked skills."""
    try:
        from tars.skills.curator import skill_curator
        if skill_curator:
            return skill_curator.get_stats()
        return []
    except ImportError:
        return []

@router.get("/pending-archive")
async def get_pending_archive(days: int = 30):
    """Skills idle beyond threshold that are candidates for archival."""
    try:
        from tars.skills.curator import skill_curator
        if skill_curator:
            return {"days": days, "items": skill_curator.get_pending_archive(days=days)}
    except ImportError:
        pass
    return {"days": days, "items": []}

@router.get("/{skill_id}/stats")
async def get_single_skill_stats(skill_id: str):
    """Get usage stats for a single skill."""
    try:
        from tars.skills.curator import skill_curator
        if skill_curator:
            return skill_curator.get_skill_stats(skill_id) or {"skill_id": skill_id, "total_calls": 0}
        return {"skill_id": skill_id, "total_calls": 0}
    except ImportError:
        return {"skill_id": skill_id, "total_calls": 0}

@router.put("/{skill_id}/archive")
async def archive_skill(skill_id: str):
    """Archive a skill (exclude from auto-activation)."""
    try:
        from tars.skills.curator import skill_curator
        if skill_curator:
            skill_curator.archive(skill_id)
        return {"status": "ok", "skill_id": skill_id, "state": "archived"}
    except ImportError:
        return {"status": "error", "message": "curator not available"}

@router.put("/{skill_id}/activate")
async def activate_skill(skill_id: str):
    """Activate an archived skill."""
    try:
        from tars.skills.curator import skill_curator
        if skill_curator:
            skill_curator.activate(skill_id)
        return {"status": "ok", "skill_id": skill_id, "state": "active"}
    except ImportError:
        return {"status": "error", "message": "curator not available"}


@router.get("/{skill_id}")
async def get_skill(skill_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    """获取技能详情"""
    tenant_id = x_tenant_id or "default"
    skill = skill_registry.get(skill_id, tenant_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")
    return {"success": True, "skill": skill.to_dict()}


@router.post("/create-prompt")
async def create_prompt_skill(request: CreatePromptSkillRequest):
    """在线创建 PromptSkill"""
    from ..skills.base import Skill, SkillParameter

    params = [
        SkillParameter(
            name=p.get("name", ""),
            type=p.get("type", "string"),
            description=p.get("description", ""),
            required=p.get("required", False),
            default=p.get("default"),
        )
        for p in request.parameters
    ]

    skill = Skill(
        id=request.id,
        name=request.name,
        description=request.description,
        type=SkillType.PROMPT,
        prompt_template=request.prompt_template,
        tags=request.tags,
        parameters=params,
        source="local",
    )

    skill_registry.register(skill)
    return {"success": True, "message": f"PromptSkill '{request.name}' 创建成功", "skill": skill.to_dict()}


@router.delete("/{skill_id}")
async def uninstall_skill(skill_id: str):
    """卸载技能"""
    skill = skill_registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")
    skill_registry.unregister(skill_id)
    return {"success": True, "message": f"技能 '{skill_id}' 已卸载"}


@router.post("/reload")
async def reload_skills():
    """重新加载所有技能"""
    if not _skill_loader:
        raise HTTPException(status_code=503, detail="SkillLoader 未初始化")
    skills = _skill_loader.reload_all()
    return {
        "success": True,
        "message": "技能重新加载完成",
        "count": len(skills),
        "skills": [s.id for s in skills],
    }


@router.put("/{skill_id}/enable")
async def enable_skill(skill_id: str):
    """启用技能"""
    if skill_registry.enable(skill_id):
        return {"success": True, "message": f"技能 '{skill_id}' 已启用"}
    raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")


@router.put("/{skill_id}/disable")
async def disable_skill(skill_id: str):
    """禁用技能"""
    if skill_registry.disable(skill_id):
        return {"success": True, "message": f"技能 '{skill_id}' 已禁用"}
    raise HTTPException(status_code=404, detail=f"技能 '{skill_id}' 不存在")
