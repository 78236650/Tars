"""Web Search 工具 — 调用本地 SearXNG 搜索引擎"""
import os
from typing import Any, Dict

import httpx

from ..base import BaseTool, ToolResult


SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "搜索网络获取最新信息。当遇到时效性问题、知识盲区、需要查找最新文档或新闻时使用。"
        "返回搜索结果列表（标题 + URL + 摘要），可配合 web_fetch 获取详情。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "最多返回结果数，默认 5，最大 10"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        limit = min(max(kwargs.get("limit", 5), 1), 10)

        if not query:
            return ToolResult(success=False, output="", error="请提供搜索关键词")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{SEARXNG_URL}/search",
                    params={"q": query, "format": "json", "engines": "google,bing,duckduckgo"},
                )
                resp.raise_for_status()

            data = resp.json()
            results = data.get("results", [])[:limit]

            if not results:
                return ToolResult(
                    success=True,
                    output="未找到相关结果",
                    metadata={"query": query, "count": 0},
                )

            lines = [f"搜索结果 (共 {len(results)} 条):\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "无标题")
                url = r.get("url", "")
                content = (r.get("content") or "")[:200]
                lines.append(f"{i}. {title}\n   {url}\n   {content}\n")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"query": query, "count": len(results)},
            )

        except httpx.ConnectError:
            return ToolResult(
                success=False,
                output="",
                error=f"无法连接 SearXNG ({SEARXNG_URL})。请确认服务已启动: docker run -d --name searxng -p 8888:8080 searxng/searxng",
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, output="", error=f"SearXNG HTTP 错误: {e.response.status_code}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")
