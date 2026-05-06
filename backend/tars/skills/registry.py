"""TARS Skills v2 - 技能注册表"""
from typing import Dict, List, Optional
from .base import Skill, SkillType


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.id] = skill

    def unregister(self, skill_id: str) -> None:
        self._skills.pop(skill_id, None)

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def list_all(self) -> List[Skill]:
        return list(self._skills.values())

    def list_enabled(self) -> List[Skill]:
        return [s for s in self._skills.values() if s.enabled]

    def list_by_type(self, skill_type: SkillType) -> List[Skill]:
        return [s for s in self._skills.values() if s.type == skill_type]

    def list_prompt_skills(self) -> List[Skill]:
        return [s for s in self._skills.values() if s.type == SkillType.PROMPT and s.enabled]

    def enable(self, skill_id: str) -> bool:
        skill = self.get(skill_id)
        if skill:
            skill.enabled = True
            return True
        return False

    def disable(self, skill_id: str) -> bool:
        skill = self.get(skill_id)
        if skill:
            skill.enabled = False
            return True
        return False

    def clear(self) -> None:
        self._skills.clear()


skill_registry = SkillRegistry()
