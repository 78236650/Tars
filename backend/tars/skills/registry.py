"""TARS Skills v2 - 技能注册表"""
from typing import Dict, List, Optional
from .base import Skill, SkillType


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.registry_key] = skill

    def unregister(self, skill_id: str, tenant_id: Optional[str] = None) -> None:
        if tenant_id:
            self._skills.pop(f"{tenant_id}:{skill_id}", None)
        self._skills.pop(skill_id, None)

    def get(self, skill_id: str, tenant_id: Optional[str] = None) -> Optional[Skill]:
        if tenant_id:
            tenant_skill = self._skills.get(f"{tenant_id}:{skill_id}")
            if tenant_skill:
                return tenant_skill
        return self._skills.get(skill_id)

    def list_all(self, tenant_id: Optional[str] = None) -> List[Skill]:
        if tenant_id:
            return self.list_for_tenant(tenant_id)
        return list(self._skills.values())

    def list_for_tenant(self, tenant_id: str) -> List[Skill]:
        visible = [
            s for s in self._skills.values()
            if s.scope == "global" or s.tenant_id == tenant_id
        ]
        tenant_overrides = {
            s.id for s in visible
            if s.scope == "tenant" and s.tenant_id == tenant_id
        }
        return [
            s for s in visible
            if not (s.scope == "global" and s.id in tenant_overrides)
        ]

    def list_enabled(self, tenant_id: Optional[str] = None) -> List[Skill]:
        skills = self.list_for_tenant(tenant_id) if tenant_id else list(self._skills.values())
        return [s for s in skills if s.enabled]

    def list_by_type(self, skill_type: SkillType, tenant_id: Optional[str] = None) -> List[Skill]:
        return [s for s in self.list_all(tenant_id) if s.type == skill_type]

    def list_prompt_skills(self, tenant_id: Optional[str] = None) -> List[Skill]:
        return [
            s for s in self.list_all(tenant_id)
            if s.type == SkillType.PROMPT and s.enabled
        ]

    def enable(self, skill_id: str, tenant_id: Optional[str] = None) -> bool:
        skill = self.get(skill_id, tenant_id)
        if skill:
            skill.enabled = True
            return True
        return False

    def disable(self, skill_id: str, tenant_id: Optional[str] = None) -> bool:
        skill = self.get(skill_id, tenant_id)
        if skill:
            skill.enabled = False
            return True
        return False

    def clear(self) -> None:
        self._skills.clear()


skill_registry = SkillRegistry()
