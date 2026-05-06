"""TARS Skills v2 - 从目录加载 Skill"""
import yaml
from pathlib import Path
from typing import List, Optional

from .base import Skill, SkillType, SkillParameter
from .registry import SkillRegistry
from ..tools.registry import ToolRegistry
from ..tools.plugin_loader import load_plugin_tool


class SkillLoader:
    """从 skills/ 目录加载所有 Skill"""

    def __init__(self, skills_dir: str = "skills", tool_registry: Optional[ToolRegistry] = None, skill_registry: Optional[SkillRegistry] = None):
        self.skills_dir = Path(skills_dir)
        self.tool_registry = tool_registry
        self.skill_registry = skill_registry

    def load_all(self) -> List[Skill]:
        """加载 skills/ 下所有子目录中的 skill.yaml"""
        loaded = []
        if not self.skills_dir.exists():
            return loaded

        for item in self.skills_dir.iterdir():
            if item.is_dir():
                yaml_path = item / "skill.yaml"
                if yaml_path.exists():
                    skill = self._load_skill(yaml_path, item)
                    if skill:
                        loaded.append(skill)
        return loaded

    def _load_skill(self, yaml_path: Path, skill_dir: Path) -> Optional[Skill]:
        """解析 skill.yaml 并加载"""
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            skill_type = SkillType(data.get("type", "prompt"))
            parameters = []
            for p in data.get("parameters", []):
                parameters.append(SkillParameter(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default=p.get("default"),
                ))

            skill = Skill(
                id=data.get("id", skill_dir.name),
                name=data.get("name", skill_dir.name),
                description=data.get("description", ""),
                type=skill_type,
                version=data.get("version", "1.0.0"),
                author=data.get("author", ""),
                tags=data.get("tags", []),
                enabled=data.get("enabled", True),
                source=data.get("source", "local"),
                permissions=data.get("permissions", []),
                dependencies=data.get("dependencies", []),
                entry_point=data.get("entry_point"),
                prompt_template=data.get("prompt_template"),
                parameters=parameters,
                _dir_path=str(skill_dir),
            )

            # 注册到 SkillRegistry
            if self.skill_registry:
                self.skill_registry.register(skill)

            # PluginSkill: 加载 Python 代码并注册为 Tool
            if skill.type == SkillType.PLUGIN and skill.entry_point and self.tool_registry:
                entry_path = skill_dir / skill.entry_point
                tool = load_plugin_tool(entry_path)
                if tool:
                    self.tool_registry.register(tool)

            return skill
        except Exception as e:
            print(f"[SkillLoader] 加载 {yaml_path} 失败: {e}")
            return None

    def save_skill(self, skill: Skill, target_dir: Optional[Path] = None) -> Path:
        """保存 Skill 到目录"""
        skill_dir = target_dir or (self.skills_dir / skill.id)
        skill_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "type": skill.type.value,
            "version": skill.version,
            "author": skill.author,
            "tags": skill.tags,
            "permissions": skill.permissions,
            "dependencies": skill.dependencies,
        }
        if skill.entry_point:
            data["entry_point"] = skill.entry_point
        if skill.prompt_template:
            data["prompt_template"] = skill.prompt_template
        if skill.parameters:
            data["parameters"] = [
                {"name": p.name, "type": p.type, "description": p.description, "required": p.required, "default": p.default}
                for p in skill.parameters
            ]

        yaml_path = skill_dir / "skill.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        return skill_dir
