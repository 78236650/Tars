"""TARS MCP (Model Context Protocol) Client Integration"""
from .client import MCPClient, MCPServerConfig, MCPToolDef, MCPError
from .tool_adapter import MCPToolAdapter, create_mcp_adapters
from .registry import MCPRegistry

__all__ = [
    "MCPClient", "MCPServerConfig", "MCPToolDef", "MCPError",
    "MCPToolAdapter", "create_mcp_adapters", "MCPRegistry",
]
