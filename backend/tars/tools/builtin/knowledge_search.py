"""知识库搜索工具 — 供 Agent 调用"""
from typing import Any, Dict, List

from tars.tools.base import BaseTool, ToolResult


class KnowledgeSearchTool(BaseTool):
    """知识库搜索工具"""

    name: str = "knowledge_search"
    description: str = (
        "搜索知识库中的文档内容。当用户询问关于上传的文档、资料、知识库中的信息时使用此工具。"
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

    def __init__(self, retriever=None):
        self._retriever = retriever

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        collection_id = kwargs.get("collection_id")
        top_k = kwargs.get("top_k", 5)

        if not query:
            return ToolResult(success=False, output="", error="查询不能为空")

        if self._retriever is None:
            return ToolResult(success=False, output="", error="知识库检索器未初始化")

        try:
            collection_ids = [collection_id] if collection_id else []
            results = self._retriever.retrieve(
                query=query,
                collection_ids=collection_ids,
                top_k=top_k,
            )

            if not results:
                return ToolResult(
                    success=True,
                    output="未找到相关内容。",
                    metadata={"results": []},
                )

            lines = [f"找到 {len(results)} 条相关内容："]
            for i, r in enumerate(results, 1):
                source = r.get("source", {})
                file_name = source.get("file_name", "未知文件")
                lines.append(f"\n[{i}] 来源: {file_name}")
                lines.append(f"内容: {r['text'][:300]}...")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"results": results},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")
