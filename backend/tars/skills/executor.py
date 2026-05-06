"""TARS Skills v2 - Skill 执行器（桥接 Skill 和 Tool 系统）"""
from typing import List

from .base import Skill, SkillType
from .registry import SkillRegistry


class SkillExecutor:
    """管理 PromptSkill 的激活和注入"""

    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry

    def get_active_prompt_skills(self) -> List[Skill]:
        """获取所有激活的 PromptSkill"""
        return self.skill_registry.list_prompt_skills()

    def build_prompt_injection(self) -> str:
        """构建所有激活 PromptSkill 的 system prompt 注入内容"""
        prompt_skills = self.get_active_prompt_skills()
        if not prompt_skills:
            return ""

        sections = []
        for skill in prompt_skills:
            if skill.prompt_template:
                sections.append(f"## {skill.name}\n{skill.prompt_template}")

        if not sections:
            return ""

        return "\n\n---\n\n".join(sections)
