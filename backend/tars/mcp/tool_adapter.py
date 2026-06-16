"""TARS MCP Tool Adapter — 将外部 MCP 工具适配为 TARS BaseTool"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from tars.tools.base import BaseTool, ToolResult
from .client import MCPClient, MCPToolDef, MCPError


class MCPToolAdapter(BaseTool):
    """将 MCP 工具包装为 TARS 原生 BaseTool，可注册到 ToolRegistry 并供 Agent 调用。"""

    def __init__(self, tdef: MCPToolDef, client: MCPClient):
        self._tdef = tdef
        self._client = client
        # 从 MCPToolDef 提取工具元信息
        self.name = tdef.name
        self.description = self._build_description(tdef)
        self.parameters_schema = tdef.input_schema or {}
        # 确保 schema 有 type: object
        if self.parameters_schema and "type" not in self.parameters_schema:
            self.parameters_schema["type"] = "object"
        # MCP 服务器信息
        self.server_name = tdef.server_name

    def _build_description(self, tdef: MCPToolDef) -> str:
        """构建带标注的描述。"""
        desc = tdef.description or tdef.name
        return f"[MCP:{tdef.server_name}] {desc}"

    async def execute(self, **kwargs) -> ToolResult:
        """执行 MCP 工具调用。"""
        try:
            result = await self._client.call_tool(self.name, kwargs)
            # MCP tools/call 返回: {"content": [...], "isError": False}
            content_items = result.get("content", [])
            is_error = result.get("isError", False)

            # 提取文本内容
            lines = []
            for item in content_items:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        lines.append(str(item.get("text", "")))
                    elif item.get("type") == "resource":
                        lines.append(f"[resource: {item.get('resource', {})}]")
                    else:
                        lines.append(json.dumps(item, ensure_ascii=False))

            output = "\n".join(lines) if lines else str(result)

            if is_error:
                return ToolResult(success=False, error=output or "MCP tool returned error")

            return ToolResult(success=True, output=output)

        except MCPError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"MCP call failed: {e}")


# ---------------------------------------------------------------------------
# Helper: 批量创建适配器
# ---------------------------------------------------------------------------

def create_mcp_adapters(client: MCPClient) -> Dict[str, MCPToolAdapter]:
    """为 MCP client 中所有已注册工具创建适配器。"""
    adapters: Dict[str, MCPToolAdapter] = {}
    for tdef in client.list_all_tools():
        adapter = MCPToolAdapter(tdef, client)
        adapters[tdef.name] = adapter
    return adapters
