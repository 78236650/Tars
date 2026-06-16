"""TARS MCP Registry — 管理 MCP 服务器的生命周期和工具注册/卸载"""
from __future__ import annotations

from typing import Dict, List, Optional
import asyncio
import logging

from .client import MCPClient, MCPServerConfig, MCPToolDef, MCPError
from .tool_adapter import MCPToolAdapter, create_mcp_adapters

logger = logging.getLogger(__name__)


class MCPRegistry:
    """管理活跃 MCP 服务器及其工具注册。"""

    def __init__(self, tool_registry=None):
        self._client = MCPClient()
        self._servers: Dict[str, MCPServerConfig] = {}
        self._adapters: Dict[str, MCPToolAdapter] = {}  # tool_name → adapter
        self._tool_registry = tool_registry  # TARS ToolRegistry（可选）

    # ------------------------------------------------------------------
    # 服务器管理
    # ------------------------------------------------------------------

    async def add_server(self, config: MCPServerConfig) -> List[MCPToolDef]:
        """添加并连接一个 MCP 服务器。

        返回该服务器提供的工具列表。
        """
        self._servers[config.name] = config
        tools = await self._client.connect_server(config)
        # 创建适配器并注册到 ToolRegistry
        adapters = create_mcp_adapters(self._client)
        for name, adapter in adapters.items():
            if adapter.server_name == config.name:
                self._adapters[name] = adapter
                if self._tool_registry:
                    self._tool_registry.register(adapter)
        logger.info(f"[MCP] 服务器 {config.name} 已连接,提供了 {len(tools)} 个工具")
        return tools

    async def remove_server(self, name: str) -> None:
        """断开并移除一个 MCP 服务器。

        同时从 ToolRegistry 卸载其所有工具。
        """
        if name not in self._servers:
            return
        # 卸载工具
        to_remove = [n for n, a in self._adapters.items() if a.server_name == name]
        for tool_name in to_remove:
            del self._adapters[tool_name]
            # ToolRegistry 目前没有 unregister 方法,但 register 会覆盖同名工具
        await self._client.disconnect_server(name)
        del self._servers[name]
        logger.info(f"[MCP] 服务器 {name} 已断开")

    async def reload_server(self, name: str) -> List[MCPToolDef]:
        """重连一个 MCP 服务器（用于配置变更后刷新工具列表）。"""
        if name not in self._servers:
            raise MCPError(f"服务器 {name} 未注册")
        # 先卸载
        to_remove = [n for n, a in self._adapters.items() if a.server_name == name]
        for tool_name in to_remove:
            del self._adapters[tool_name]
        await self._client.disconnect_server(name)
        # 重连
        tools = await self._client.connect_server(self._servers[name])
        adapters = create_mcp_adapters(self._client)
        for aname, adapter in adapters.items():
            if adapter.server_name == name:
                self._adapters[aname] = adapter
                if self._tool_registry:
                    self._tool_registry.register(adapter)
        logger.info(f"[MCP] 服务器 {name} 已重连,提供了 {len(tools)} 个工具")
        return tools

    async def shutdown(self) -> None:
        """断开所有连接。"""
        await self._client.disconnect_all()
        self._servers.clear()
        self._adapters.clear()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_servers(self) -> List[MCPServerConfig]:
        return list(self._servers.values())

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        return self._servers.get(name)

    def list_adapters(self) -> Dict[str, MCPToolAdapter]:
        return dict(self._adapters)
