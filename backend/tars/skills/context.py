"""SkillContext — v2.2 技能 Hook 上下文"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SkillContext:
    """暴露给 Hook 函数的上下文"""
    working_context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    system_prompt_parts: List[str] = field(default_factory=list)
    tool_registry: Any = None
    skill_state: Dict[str, Any] = field(default_factory=dict)
    response_patches: List[Callable] = field(default_factory=list)

    def set_response_patch(self, fn: Callable):
        """注册主 LLM 回复后处理函数"""
        self.response_patches.append(fn)

    def append_to_prompt(self, text: str):
        """向 system prompt 追加内容"""
        self.system_prompt_parts.append(text)

    def register_tool(self, tool: Any):
        """临时注册工具（仅本轮生效）"""
        if self.tool_registry:
            self.tool_registry.register(tool)

    def disable_tool(self, tool_name: str):
        """临时禁用工具"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
