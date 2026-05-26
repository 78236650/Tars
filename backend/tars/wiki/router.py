import re
from typing import Optional, Callable, Awaitable

MEETING_KEYWORDS = re.compile(r"(会议|纪要|meeting|minutes|周会|例会|晨会|站会)")


class WikiRagRouter:
    def __init__(self, llm_provider: Optional[Callable[..., Awaitable[str]]] = None):
        self.llm_provider = llm_provider

    def route(
        self,
        page_count: Optional[int] = None,
        text_size: int = 0,
        file_name: str = "",
        file_format: str = "",
        has_abstract: bool = False,
        user_override: Optional[str] = None,
    ) -> str:
        if user_override:
            return user_override

        if (page_count and page_count > 15) or text_size > 50000:
            return "rag"
        if has_abstract and file_format == "pdf":
            return "rag"
        if MEETING_KEYWORDS.search(file_name):
            return "wiki"
        if text_size < 10000 and file_format in ("md", "txt"):
            return "wiki"

        return "llm_decide"

    async def route_with_llm_fallback(
        self,
        page_count: Optional[int] = None,
        text_size: int = 0,
        file_name: str = "",
        file_format: str = "",
        has_abstract: bool = False,
        user_override: Optional[str] = None,
        text_preview: str = "",
    ) -> str:
        decision = self.route(
            page_count=page_count, text_size=text_size,
            file_name=file_name, file_format=file_format,
            has_abstract=has_abstract, user_override=user_override,
        )
        if decision != "llm_decide":
            return decision

        if not self.llm_provider:
            return "rag"

        prompt = (
            f"判断以下文件适合编译进结构化 wiki（适合综合归纳、频繁引用的内容）"
            f"还是作为 RAG 检索源保留原文（适合大文档、需要精确引用）。\n\n"
            f"文件名: {file_name}\n格式: {file_format}\n"
            f"页数: {page_count}\n文本量: {text_size} 字符\n"
            f"内容预览: {text_preview[:500]}\n\n"
            f"只回答 wiki 或 rag，不要解释。"
        )
        result = await self.llm_provider(prompt)
        return "wiki" if "wiki" in result.lower() else "rag"
