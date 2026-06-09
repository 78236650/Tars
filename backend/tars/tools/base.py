"""TARS Tools - 基础类定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    # v5.0.5/A1: 健壮性信号 —— 供 agent 循环判断失败是否可恢复/值得重试,
    # 以及 output 是否因超长被截断。均为附加字段,默认不影响既有构造。
    recoverable: bool = True
    retry_suggested: bool = False
    truncated: bool = False


class BaseTool(ABC):
    """工具抽象基类"""

    name: str = "base_tool"
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_function_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
