"""Wiki 全文搜索工具 — 支持向量相似度 + 关键词混合搜索。"""
from tars.tools.base import BaseTool, ToolResult
from tars.wiki.store import WikiStore


class WikiSearchTool(BaseTool):
    name: str = "wiki_search"
    description: str = (
        "在 Wiki 知识库中全文搜索相关内容。传入 query 搜索词，返回匹配的页面名、摘要和相关度分数。"
        "适用场景：不确定信息在哪个页面时，用此工具模糊搜索；确定页面名后，再用 read_wiki 读取完整内容。"
    )
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或自然语言查询",
            },
            "top_k": {
                "type": "integer",
                "description": "返回的结果数量，默认 5",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, store: WikiStore):
        self.store = store

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(success=False, output="请提供搜索关键词 query")

        top_k = int(kwargs.get("top_k", 5))
        results = self.store.search(query, top_k=top_k)

        if not results:
            return ToolResult(
                success=True,
                output=f"未找到与「{query}」相关的 Wiki 页面。"
            )

        lines = [f"搜索「{query}」找到 {len(results)} 个结果：\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] **{r['page_name']}** (相关度: {r['score']:.2f})\n"
                f"    {r['snippet']}\n"
            )
        return ToolResult(success=True, output="\n".join(lines))
