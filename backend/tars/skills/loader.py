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
        """加载 skills/ 下所有子目录中的 skill.yaml + SKILL.md"""
        loaded = []
        if not self.skills_dir.exists():
            return loaded

        for item in self.skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # SKILL.md 优先（v2.5），fallback skill.yaml
                md_path = item / "SKILL.md"
                yaml_path = item / "skill.yaml"
                if md_path.exists():
                    skill = self._load_skill_md(md_path, item)
                elif yaml_path.exists():
                    skill = self._load_skill(yaml_path, item)
                else:
                    continue
                if skill:
                    loaded.append(skill)
        return loaded

    def _load_skill_md(self, md_path: Path, skill_dir: Path) -> Optional[Skill]:
        """解析 SKILL.md（v2.5 Agent Skills 规范）"""
        try:
            from .skill_md_parser import parse_skill_md
            smd = parse_skill_md(str(md_path))
            if not smd:
                return None

            # 若目录下有 main.py，按 PLUGIN 型加载（保留 v2.2 Python 技能能力）
            entry_path = skill_dir / "main.py"
            is_plugin = entry_path.exists()

            skill = Skill(
                id=smd.name,
                name=smd.name,
                description=smd.description,
                type=SkillType("plugin") if is_plugin else SkillType("prompt"),
                prompt_template=smd.body,
                entry_point="main.py" if is_plugin else None,
                permissions=smd.permissions,
                tars_version_min=smd.tars_version_min,
                requires_packages=smd.requires_packages,
                source="local",
                _dir_path=str(skill_dir),
            )

            if self.skill_registry:
                self.skill_registry.register(skill)

            # PluginSkill: 加载 Python 代码并注册为 Tool
            if is_plugin and self.tool_registry:
                tool = load_plugin_tool(entry_path)
                if tool:
                    self.tool_registry.register(tool)

            # 存到 skills_v3 表
            try:
                db = getattr(self, '_db', None)
                if db:
                    import json, datetime
                    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
                    conn = db._get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR REPLACE INTO skills_v3 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (smd.name, smd.name, smd.description, "local",
                         str(skill_dir), int(smd.has_pdca), int(smd.has_scripts),
                         json.dumps(smd.permissions, ensure_ascii=False),
                         json.dumps(smd.permissions, ensure_ascii=False),
                         now, 1),
                    )
                    conn.commit()
            except Exception:
                pass

            return skill
        except Exception as e:
            print(f"[SkillLoader] 加载 SKILL.md {md_path} 失败: {e}")
            return None

    def get_progressive_disclosure(self) -> str:
        """返回渐进披露文本——所有已启用技能的 name + description 列表"""
        skills = self.skill_registry.list_enabled() if self.skill_registry else []
        if not skills:
            return ""

        lines = ["## 可用技能 (Skills)", ""]
        for s in skills:
            desc = getattr(s, 'description', '') or ''
            lines.append(f"- **{s.name}**: {desc}")
        return "\n".join(lines)

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

            trigger = data.get("trigger", {}) or {}
            hooks = data.get("hooks", {}) or {}

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
                tars_version_min=data.get("tars_version_min"),
                requires_packages=data.get("requires_packages", []),
                usage=data.get("usage"),
                entry_point=data.get("entry_point"),
                prompt_template=data.get("prompt_template"),
                parameters=parameters,
                trigger_intents=trigger.get("intents", []),
                trigger_entities=trigger.get("entities", []),
                trigger_keywords=trigger.get("keywords", []),
                trigger_conditions=trigger.get("conditions", "any"),
                priority=data.get("priority", 50),
                lifecycle=data.get("lifecycle", "per_turn"),
                hooks=hooks,
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
        if skill.tars_version_min:
            data["tars_version_min"] = skill.tars_version_min
        if skill.requires_packages:
            data["requires_packages"] = skill.requires_packages
        if skill.usage:
            data["usage"] = skill.usage
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
