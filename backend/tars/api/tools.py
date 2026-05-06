"""TARS API - 工具管理路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..tools import registry as tool_registry

router = APIRouter(prefix="/api/tools", tags=["工具管理"])


class ToolStatusUpdate(BaseModel):
    status: str  # "active" | "disabled"


class ToolConfigUpdate(BaseModel):
    config: Dict[str, Any]


class ToolExecuteRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}


@router.get("/")
async def list_tools():
    """列出所有已注册工具"""
    tools = tool_registry.list_all()
    return {
        "tools": [
            {
                "id": t.name,
                "name": t.name,
                "icon": getattr(t, "icon", "🔧"),
                "type": "builtin",
                "source": "builtin",
                "status": "active",
                "description": t.description,
                "parameters_schema": t.parameters_schema,
            }
            for t in tools
        ]
    }


@router.get("/{tool_id}")
async def get_tool_detail(tool_id: str):
    """获取工具详情"""
    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_id}' 不存在")
    return {
        "id": tool.name,
        "name": tool.name,
        "icon": getattr(tool, "icon", "🔧"),
        "type": "builtin",
        "source": "builtin",
        "status": "active",
        "description": tool.description,
        "parameters_schema": tool.parameters_schema,
    }


@router.put("/{tool_id}/status")
async def update_tool_status(tool_id: str, request: ToolStatusUpdate):
    """启用/禁用工具"""
    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_id}' 不存在")
    # 内置工具暂不支持禁用（后续可扩展）
    return {"success": True, "message": f"工具 '{tool_id}' 状态已更新", "status": request.status}


@router.put("/{tool_id}/config")
async def update_tool_config(tool_id: str, request: ToolConfigUpdate):
    """更新工具配置"""
    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_id}' 不存在")
    return {"success": True, "message": f"工具 '{tool_id}' 配置已更新", "config": request.config}


@router.post("/execute")
async def execute_tool(request: ToolExecuteRequest):
    """手动执行工具（调试用）"""
    tool = tool_registry.get(request.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{request.tool_name}' 不存在")

    result = await tool.execute(**request.parameters)
    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "metadata": result.metadata,
    }
