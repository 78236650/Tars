"""混合搜索 — 语义 + FTS 关键词 + Ebbinghaus 衰减 + 命中强化"""
from typing import List

from .deduplicator import cosine_similarity
from .embeddings import EmbeddingProvider, deserialize_vector
from .decay import decay_score, hours_since


def _semantic_skip_reason(exc: BaseException) -> str:
    """将常见瞬时错误转成人话，便于对照日志。"""
    msg = str(exc).lower()
    if "client has been closed" in msg or ("closed" in msg and "client" in msg):
        return "嵌入/下载 HTTP 客户端已关闭（常见于热重载、进程退出或并发切换），已仅用关键词检索"
    if "timed out" in msg or "timeout" in msg:
        return "嵌入或 Hub 请求超时，已仅用关键词检索"
    if "connection refused" in msg or "connection reset" in msg:
        return "网络连接被拒绝或重置，已仅用关键词检索"
    if "cannot send a request" in msg:
        return "HTTP 客户端不可用，已仅用关键词检索"
    return f"{type(exc).__name__}: {exc}，已仅用关键词检索"


class HybridSearch:
    """语义搜索 + FTS 关键词搜索 + 衰减加权"""

    def __init__(
        self,
        db,
        embedding_provider: EmbeddingProvider = None,
        tenant_id: str = "default",
        vector_store=None,
        reranker=None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.tenant_id = tenant_id
        self.vector_store = vector_store
        self.reranker = reranker

    def search(self, query: str, limit: int = 5) -> list:
        """混合搜索 + 衰减加权 + 命中强化"""
        scored: dict = {}  # mem_id -> (mem, score)

        # 1. 语义搜索（优先使用 Chroma 向量数据库）
        semantic_hits = 0
        if self.vector_store and self.vector_store.is_available:
            try:
                self._chroma_semantic_score(query, scored)
                semantic_hits = len(scored)
            except Exception as e:
                print(f"[HybridSearch] Chroma search failed: {e}, fallback to SQLite")
                # Chroma 失败时回退到 SQLite BLOB
                if self.embedding_provider:
                    try:
                        self._sqlite_semantic_score(query, scored)
                        semantic_hits = len(scored)
                    except Exception as e2:
                        print(f"[HybridSearch] {_semantic_skip_reason(e2)}")
        elif self.embedding_provider:
            try:
                self._sqlite_semantic_score(query, scored)
                semantic_hits = len(scored)
            except Exception as e:
                print(f"[HybridSearch] {_semantic_skip_reason(e)}")

        # 2. FTS 关键词搜索作为补充
        kw_hits = 0
        try:
            prev_count = len(scored)
            self._keyword_score(query, scored)
            kw_hits = len(scored) - prev_count
        except Exception:
            pass

        # 3. 排序取 top（或 reranker 重排）
        if self.reranker and scored:
            candidates = [{"text": mem.content, "score": score, "original": mem} for mem, score in scored.values()]
            reranked = self.reranker.rerank(query, candidates, top_k=limit, text_key="text")
            results = [item["original"] for item in reranked]
        else:
            ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]
            results = [mem for mem, _ in ranked]

        # 4. 命中强化
        for mem in results:
            try:
                self.db.reinforce_memory(mem.id, tenant_id=self.tenant_id)
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

    def _chroma_semantic_score(self, query: str, scored: dict):
        """使用 Chroma 向量数据库进行语义搜索"""
        chroma_results = self.vector_store.query(
            query_text=query,
            top_k=20,  # 召回更多，后续排序取 top
            tenant_id=self.tenant_id,
            collection_name="memories",
        )

        for item in chroma_results:
            mem_id = item["id"]
            distance = item["distance"]
            # Chroma 返回的是 L2 距离，转换为相似度 (0-1)
            sim = max(0.0, 1.0 - distance)

            # 获取记忆完整信息
            mem = self.db.get_memory(mem_id, tenant_id=self.tenant_id)
            if not mem:
                continue

            importance = getattr(mem, "importance", 0.5) or 0.5
            last_accessed = getattr(mem, "last_accessed", None)
            age_h = hours_since(last_accessed) if last_accessed else 0
            score = decay_score(sim, importance, age_h)
            scored[mem_id] = (mem, score)

    def _sqlite_semantic_score(self, query: str, scored: dict):
        """使用 SQLite BLOB 进行语义搜索（回退方案）"""
        query_vec = self.embedding_provider.encode([query])[0]
        all_memories = self.db.get_all_memories_with_metadata(tenant_id=self.tenant_id)
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
        keyword_results = self.db.search_memories(query, limit=10, tenant_id=self.tenant_id)
        for mem in keyword_results:
            if mem.id in scored:
                continue
            # 关键词命中给固定基础分，再叠加衰减/重要性
            importance = getattr(mem, "importance", 0.5) or 0.5
            score = decay_score(0.5, importance, 0)  # 假设 last_accessed=now
            scored[mem.id] = (mem, score)
