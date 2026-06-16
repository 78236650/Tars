"""TARS Tools - 唯一注册中心"""
from typing import Dict, List, Optional
from .base import BaseTool


class ToolRegistry:
    """工具注册表 - 全局唯一"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        # 延迟加载，防止循环引用
        self._mcp_registry = None

    def _get_mcp_registry(self):
        if self._mcp_registry is None:
            try:
                from ..mcp.registry import mcp_registry
                self._mcp_registry = mcp_registry
            except ImportError:
                self._mcp_registry = False  # Failed to load
        return self._mcp_registry if self._mcp_registry is not False else None

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        tool = self._tools.get(name)
        if tool:
            return tool
        mcp_reg = self._get_mcp_registry()
        if mcp_reg:
            return mcp_reg.get_tool(name)
        return None

    def list_all(self) -> List[BaseTool]:
        tools = list(self._tools.values())
        mcp_reg = self._get_mcp_registry()
        if mcp_reg:
            tools.extend(mcp_reg.get_all_tools())
        return tools

    def list_names(self) -> List[str]:
        return [t.name for t in self.list_all()]

    def get_function_schemas(self) -> List[Dict]:
        return [tool.to_function_schema() for tool in self.list_all()]

    def clear(self) -> None:
        self._tools.clear()


registry = ToolRegistry()
