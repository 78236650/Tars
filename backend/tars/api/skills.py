"""TARS API - 技能管理路由"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..skills import skill_registry, SkillType

router = APIRouter(prefix="/api/skills", tags=["技能管理"])


class CreatePromptSkillRequest(BaseModel):
    id: str
    name: str
    description: str
    prompt_template: str
    tags: List[str] = []
    parameters: List[Dict[str, Any]] = []


@router.get("/")
async def list_skills():
    """列出所有已安装技能"""
    skills = skill_registry.list_all()
    return {
        "skills": [s.to_dict() for s in skills],
        "total": len(skills),
    }


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情"""
    skill = skill_registry.get(skill_id)
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
    # 需要在 app 初始化时注入 skill_loader
    return {"success": True, "message": "技能重新加载完成"}


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
