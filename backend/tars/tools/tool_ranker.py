"""TARS 分层工具发现 — 动态 Top-K 工具匹配

使用 CrossEncoder 对工具描述和用户查询做相关性排序，
将全量注入 (34 tools) 缩减为 Top-K 注入，缓解 Token 压力。
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any


class ToolRanker:
    """基于 CrossEncoder 的工具相关性排序器。

    用法:
        ranker = ToolRanker(reranker_model)
        top_k_tools = ranker.rank(query, all_tools, top_k=10)
    """

    def __init__(self, reranker=None):
        self._reranker = reranker  # CrossEncoderReranker 实例

    @property
    def is_available(self) -> bool:
        return self._reranker is not None

    def rank(
        self,
        query: str,
        tools: List[Dict[str, Any]],
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """对工具列表按用户查询相关性排序，返回 Top-K。

        Args:
            query: 用户最近的输入文本
            tools: 工具 schema 列表 (每项含 function.name + function.description)
            top_k: 返回数量
            min_score: 最低相关性分数阈值 (0-1)
        """
        if not tools:
            return []
        if not self.is_available or len(tools) <= top_k:
            return tools[:top_k]

        # 构建排序候选
        candidates = []
        for t in tools:
            fn = t.get("function", {})
            desc = fn.get("description", "")
            name = fn.get("name", "")
            text = f"{name}: {desc}" if desc else name
            candidates.append({"text": text, "original": t})

        # 使用 reranker 排序
        try:
            ranked = self._reranker.rerank(
                query=query,
                documents=candidates,
                top_k=top_k,
                text_key="text",
            )
            # 过滤低分项
            result = []
            for item in ranked:
                score = item.get("rerank_score", 0)
                if score < min_score:
                    continue
                result.append(item["original"])
            return result
        except Exception:
            # 降级：返回前 top_k 个（保持基本功能）
            return tools[:top_k]

    def rank_by_fts(
        self,
        query: str,
        tools: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """降级方案: 基于关键词 FTS 排序（无需 CrossEncoder）。

        按工具名和描述中匹配到的关键词数量排序。
        """
        if not tools or len(tools) <= top_k:
            return tools[:top_k]

        query_lower = query.lower()
        keywords = set(query_lower.split())

        scored = []
        for t in tools:
            fn = t.get("function", {})
            text = (fn.get("name", "") + " " + fn.get("description", "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for s, t in scored[:top_k] if s > 0] or [scored[0][1]]  # 至少返回一个
