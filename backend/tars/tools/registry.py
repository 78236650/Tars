"""TARS Tools - 唯一注册中心"""
from typing import Dict, List, Optional
from .base import BaseTool


class ToolRegistry:
    """工具注册表 - 全局唯一"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_function_schemas(self) -> List[Dict]:
        return [tool.to_function_schema() for tool in self._tools.values()]

    def clear(self) -> None:
        self._tools.clear()


registry = ToolRegistry()
