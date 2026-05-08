"""混合搜索 — 语义 + FTS 关键词 + Ebbinghaus 衰减 + 命中强化"""
from typing import List, Tuple

from .deduplicator import cosine_similarity
from .embeddings import EmbeddingProvider, deserialize_vector
from .decay import decay_score, hours_since


class HybridSearch:
    """语义搜索 + FTS 关键词搜索 + 衰减加权"""

    def __init__(self, db, embedding_provider: EmbeddingProvider = None):
        self.db = db
        self.embedding_provider = embedding_provider

    def search(self, query: str, limit: int = 5) -> list:
        """混合搜索 + 衰减加权 + 命中强化"""
        scored: dict = {}  # mem_id -> (mem, score)

        # 1. 语义搜索（如有 embedding）
        semantic_hits = 0
        if self.embedding_provider:
            try:
                self._semantic_score(query, scored)
                semantic_hits = len(scored)
            except Exception as e:
                print(f"[HybridSearch] 语义搜索失败: {e}")

        # 2. FTS 关键词搜索作为补充
        kw_hits = 0
        try:
            prev_count = len(scored)
            self._keyword_score(query, scored)
            kw_hits = len(scored) - prev_count
        except Exception:
            pass

        # 3. 排序取 top
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]
        results = [mem for mem, _ in ranked]

        # 4. 命中强化
        for mem in results:
            try:
                self.db.reinforce_memory(mem.id)
            except Exception:
                pass

        # 5. 检索日志
        top_preview = ", ".join(
            f"[{m.category}]{m.content[:30]}" for m in results[:3]
        ) if results else "无命中"
        print(
            f"[HybridSearch] query=\"{query[:40]}\" "
            f"semantic={semantic_hits} keyword={kw_hits} "
            f"top={len(results)} | {top_preview}"
        )

        return results

    def _semantic_score(self, query: str, scored: dict):
        query_vec = self.embedding_provider.encode([query])[0]
        all_memories = self.db.get_all_memories_with_metadata()
        for mem, embedding_blob, last_accessed_iso, importance, _source in all_memories:
            if not embedding_blob:
                continue
            mem_vec = deserialize_vector(embedding_blob)
            if not mem_vec:
                continue
            sim = cosine_similarity(query_vec, mem_vec)
            age_h = hours_since(last_accessed_iso)
            score = decay_score(sim, importance, age_h)
            scored[mem.id] = (mem, score)

    def _keyword_score(self, query: str, scored: dict):
        keyword_results = self.db.search_memories(query, limit=10)
        for mem in keyword_results:
            if mem.id in scored:
                continue
            # 关键词命中给固定基础分，再叠加衰减/重要性
            importance = getattr(mem, "importance", 0.5) or 0.5
            score = decay_score(0.5, importance, 0)  # 假设 last_accessed=now
            scored[mem.id] = (mem, score)
