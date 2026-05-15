"""查询扩展 — 基于 LLM 生成同义词/相关词"""
from typing import List


class QueryExpander:
    """查询扩展器"""

    def __init__(self, provider=None):
        self.provider = provider

    def expand(self, query: str, method: str = "llm") -> List[str]:
        """
        扩展查询
        返回: [原始查询, 扩展查询1, 扩展查询2, ...]
        """
        if not query or not query.strip():
            return []

        results = [query]

        if method in ("llm", "hybrid") and self.provider:
            llm_expansions = self._llm_expand(query)
            results.extend(llm_expansions)

        if method in ("synonym", "hybrid"):
            synonym_expansions = self._synonym_expand(query)
            results.extend(synonym_expansions)

        # 去重
        seen = set()
        unique = []
        for q in results:
            q_lower = q.lower().strip()
            if q_lower and q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)

        return unique[:5]  # 最多返回 5 个查询

    def _llm_expand(self, query: str) -> List[str]:
        """使用 LLM 生成扩展查询"""
        if not self.provider:
            return []

        prompt = f"""请为以下查询生成 3 个同义或相关的搜索查询，帮助找到更多信息。

原始查询：{query}

请只返回查询列表，每行一个，不要包含编号或其他内容。"""

        try:
            from tars.channels.base import ChannelMessage
            import asyncio

            msg = ChannelMessage(role="user", content=prompt)
            # 使用 run_until_complete 处理异步调用
            loop = asyncio.get_event_loop()
            response = loop.run_until_complete(self.provider.complete([msg]))
            content = response.content if hasattr(response, "content") else str(response)

            expansions = [line.strip() for line in content.strip().split("\n") if line.strip()]
            return expansions[:3]
        except Exception as e:
            print(f"[QueryExpander] LLM 扩展失败: {e}")
            return []

    def _synonym_expand(self, query: str) -> List[str]:
        """基于简单规则扩展（中文同义词）"""
        # 简单的同义词映射
        synonyms = {
            "怎么": ["如何", "怎样"],
            "什么": ["哪些", "啥"],
            "问题": ["故障", "错误", "bug"],
            "使用": ["用法", "操作", "调用"],
            "安装": ["部署", "配置", "搭建"],
            "删除": ["移除", "清空", "卸载"],
            "创建": ["新建", "生成", "添加"],
            "修改": ["编辑", "更新", "更改"],
            "查询": ["搜索", "查找", "检索"],
            "数据": ["信息", "资料", "记录"],
        }

        expansions = []
        for key, values in synonyms.items():
            if key in query:
                for val in values:
                    new_query = query.replace(key, val)
                    if new_query != query:
                        expansions.append(new_query)

        return expansions[:3]
