"""记忆管理工具"""
from typing import Any, Dict, Optional

from ..base import BaseTool, ToolResult


class MemoryTool(BaseTool):
    name: str = "memory"
    description: str = "管理 Agent 的长期记忆，支持添加、搜索、列出和删除记忆。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "list", "delete"],
                "description": "操作类型",
            },
            "content": {"type": "string", "description": "记忆内容（add 时必填）"},
            "category": {"type": "string", "description": "分类: user_preference/important_decision/project_record/general"},
            "query": {"type": "string", "description": "搜索关键词（search 时必填）"},
            "memory_id": {"type": "string", "description": "记忆ID（delete 时必填）"},
            "limit": {"type": "integer", "description": "返回数量限制，默认10"},
        },
        "required": ["action"],
    }

    def __init__(self, db=None):
        self.db = db

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")
        content = kwargs.get("content")
        category = kwargs.get("category", "general")
        query = kwargs.get("query")
        memory_id = kwargs.get("memory_id")
        limit = kwargs.get("limit", 10)

        if not self.db:
            return ToolResult(success=False, output="", error="数据库未初始化")

        try:
            if action == "add":
                if not content:
                    return ToolResult(success=False, output="", error="请提供记忆内容")
                from ..base import ToolResult
                mem = self.db.add_memory(content, category)
                return ToolResult(success=True, output=f"记忆已保存 (ID: {mem.id})", metadata={"memory_id": mem.id})

            elif action == "search":
                if not query:
                    return ToolResult(success=False, output="", error="请提供搜索关键词")
                memories = self.db.search_memories(query, limit)
                lines = [f"找到 {len(memories)} 条相关记忆:"]
                for m in memories:
                    lines.append(f"  [{m.category}] {m.content}")
                return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(memories)})

            elif action == "list":
                memories = self.db.get_recent_memories(limit)
                lines = [f"最近 {len(memories)} 条记忆:"]
                for m in memories:
                    lines.append(f"  [{m.category}] {m.content}")
                return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(memories)})

            elif action == "delete":
                if not memory_id:
                    return ToolResult(success=False, output="", error="请提供记忆ID")
                self.db.delete_memory(memory_id)
                return ToolResult(success=True, output=f"记忆 {memory_id} 已删除")

            return ToolResult(success=False, output="", error=f"未知操作: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"记忆操作失败: {e}")
