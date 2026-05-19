"""知识库搜索工具 — 供 Agent 调用"""
from typing import Any, Dict

from tars.knowledge.access import search_knowledge
from tars.tools.base import BaseTool, ToolResult


class KnowledgeSearchTool(BaseTool):
    """知识库搜索工具"""

    name: str = "knowledge_search"
    description: str = (
        "搜索知识库中的文档和会议纪要。回答用户问题前应优先调用此工具检查是否有相关资料。"
        "适用场景：用户提问涉及项目信息、历史决策、会议内容、技术方案、业务知识时，都应先搜索知识库。"
        "支持自然语言查询，返回最相关的文档片段。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询，使用自然语言描述你想找的内容",
            },
            "collection_id": {
                "type": "string",
                "description": "知识库 ID（可选，不指定则搜索所有知识库）",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认 5",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, retriever=None, db=None):
        self._retriever = retriever
        self._db = db

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        collection_id = kwargs.get("collection_id")
        top_k = kwargs.get("top_k", 5)
        tenant_id = (kwargs.get("tenant_id") or "default").strip() or "default"

        if not query:
            return ToolResult(success=False, output="", error="查询不能为空")

        if self._retriever is None:
            return ToolResult(success=False, output="", error="知识库检索器未初始化")

        if self._db is None:
            return ToolResult(success=False, output="", error="知识库数据库未初始化")

        try:
            text, results = search_knowledge(
                self._db,
                self._retriever,
                query=query,
                tenant_id=tenant_id,
                collection_id=collection_id,
                top_k=top_k,
            )
            return ToolResult(
                success=True,
                output=text,
                metadata={"results": results, "count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")
