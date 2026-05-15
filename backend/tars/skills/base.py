"""TARS Skills v2 - 基础数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillType(Enum):
    PLUGIN = "plugin"
    PROMPT = "prompt"


@dataclass
class SkillParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Optional[Any] = None


@dataclass
class Skill:
    id: str
    name: str
    description: str
    type: SkillType
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    source: str = "local"  # "local" | "skillhub"
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    output_config: Dict[str, Any] = field(default_factory=dict)
    # 兼容性元数据
    tars_version_min: Optional[str] = None      # 最低 TARS 版本要求
    requires_packages: List[str] = field(default_factory=list)  # Python 包依赖
    usage: Optional[str] = None                  # 人类可读的用法说明
    # PluginSkill
    entry_point: Optional[str] = None
    # PromptSkill
    prompt_template: Optional[str] = None
    parameters: List[SkillParameter] = field(default_factory=list)
    # v2.2 SkillRouter
    trigger_intents: List[str] = field(default_factory=list)
    trigger_entities: List[str] = field(default_factory=list)
    trigger_keywords: List[str] = field(default_factory=list)
    trigger_conditions: str = "any"
    priority: int = 50
    lifecycle: str = "per_turn"
    hooks: Dict[str, str] = field(default_factory=dict)
    # 内部状态
    _dir_path: Optional[str] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "enabled": self.enabled,
            "source": self.source,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "output_config": self.output_config,
            "tars_version_min": self.tars_version_min,
            "requires_packages": self.requires_packages,
            "usage": self.usage,
            "entry_point": self.entry_point,
            "prompt_template": self.prompt_template,
            "parameters": [
                {"name": p.name, "type": p.type, "description": p.description, "required": p.required, "default": p.default}
                for p in self.parameters
            ],
        }
