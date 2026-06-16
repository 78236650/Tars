"""混合搜索 — 语义 + FTS 关键词 + Ebbinghaus 衰减 + 命中强化"""
from typing import List, Optional

from .deduplicator import cosine_similarity
from .embeddings import EmbeddingProvider, deserialize_vector
from .decay import decay_score, hours_since
from ..org import ORG_ID
from ..vectorstore.scope import memory_visibility_filter


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
        tenant_id: str = ORG_ID,
        vector_store=None,
        reranker=None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.tenant_id = tenant_id
        self.vector_store = vector_store
        self.reranker = reranker
        # v5.0.5/A3: 最近一次检索的降级深度,供调用方/调试观测。
        #   0 = Chroma 向量;1 = SQLite BLOB 向量;2 = 仅关键词;3 = 确定性向量兜底
        self.last_fallback_depth: int = 0
        self._deterministic_provider = None  # 懒加载

    def _ensure_embedding_provider(self):
        """无可用 embedding provider 时,惰性回退到确定性向量(v5.0.5/A3),
        保证离线/降级环境下语义路径不被完全跳过。"""
        if self.embedding_provider is not None:
            return self.embedding_provider
        if self._deterministic_provider is None:
            try:
                from .embeddings import DeterministicEmbeddingProvider
                self._deterministic_provider = DeterministicEmbeddingProvider()
            except Exception:
                return None
        return self._deterministic_provider

    def search(self, query: str, limit: int = 5) -> list:
        """混合搜索 + 衰减加权 + 命中强化"""
        scored: dict = {}  # mem_id -> (mem, score)
        fallback_depth = 0

        # 1. 语义搜索（优先使用 Chroma 向量数据库）
        semantic_hits = 0
        if self.vector_store and self.vector_store.is_available:
            try:
                self._chroma_semantic_score(query, scored)
                semantic_hits = len(scored)
                fallback_depth = 0
            except Exception as e:
                print(f"[HybridSearch] Chroma search failed: {e}, fallback to SQLite")
                # Chroma 失败时回退到 SQLite BLOB
                if self.embedding_provider:
                    try:
                        self._sqlite_semantic_score(query, scored)
                        semantic_hits = len(scored)
                        fallback_depth = 1
                    except Exception as e2:
                        print(f"[HybridSearch] {_semantic_skip_reason(e2)}")
                        fallback_depth = 2
                else:
                    fallback_depth = 2
        elif self.embedding_provider:
            try:
                self._sqlite_semantic_score(query, scored)
                semantic_hits = len(scored)
                fallback_depth = 1
            except Exception as e:
                print(f"[HybridSearch] {_semantic_skip_reason(e)}")
                fallback_depth = 2
        else:
            # 无任何 embedding provider:尝试确定性向量兜底
            provider = self._ensure_embedding_provider()
            if provider is not None:
                try:
                    self._sqlite_semantic_score(query, scored, provider=provider)
                    semantic_hits = len(scored)
                    fallback_depth = 3
                except Exception as e:
                    print(f"[HybridSearch] {_semantic_skip_reason(e)}")
                    fallback_depth = 2
            else:
                fallback_depth = 2

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

        # 5. 记录降级深度 + 检索日志
        self.last_fallback_depth = fallback_depth
        top_preview = ", ".join(
            f"[{m.category}]{m.content[:30]}" for m in results[:3]
        ) if results else "无命中"
        print(
            f"[HybridSearch] query=\"{query[:40]}\" "
            f"semantic={semantic_hits} keyword={kw_hits} "
            f"fallback_depth={fallback_depth} "
            f"top={len(results)} | {top_preview}"
        )

        return results

    def _resolve_viewer_user_id(self, user_id: Optional[str] = None) -> Optional[str]:
        if user_id is not None:
            return user_id
        try:
            from tars.context import get_current_user_id
            return get_current_user_id()
        except RuntimeError:
            return None

    def _chroma_semantic_score(self, query: str, scored: dict):
        """使用 Chroma 向量数据库进行语义搜索"""
        viewer_id = self._resolve_viewer_user_id()
        chroma_results = self.vector_store.query(
            query_text=query,
            top_k=20,  # 召回更多，后续排序取 top
            tenant_id=self.tenant_id,
            collection_name="memories",
            filter_dict=memory_visibility_filter(viewer_id),
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
            score = self._adjust_score(score, mem)
            scored[mem_id] = (mem, score)

    def _sqlite_semantic_score(self, query: str, scored: dict, provider=None):
        """使用 SQLite BLOB 进行语义搜索（回退方案）。

        provider 显式传入时用之(确定性向量兜底),否则用实例的 embedding_provider。
        """
        emb = provider or self.embedding_provider
        query_vec = emb.encode([query])[0]
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
            score = self._adjust_score(score, mem)
            scored[mem.id] = (mem, score)
    @staticmethod
    def _adjust_score(base_score: float, mem) -> float:
        """检索后微调：solution/procedural boost，pinned boost，compressed discount。

        solution 类记忆是结构化的解决思路，乘以 1.15 提升排名；
        procedural 记忆是步骤/SOP，同样提升；
        pinned 记忆是用户标记的重要记忆，乘以 1.2；
        compressed 记忆是合并产物，已丢失细节，乘以 0.9 轻度降权。
        """
        score = base_score
        category = (getattr(mem, "category", "") or "").lower()
        memory_type = (getattr(mem, "memory_type", "") or "").lower()
        if category in ("solution", "correction", "lesson_learned") or memory_type == "procedural":
            score *= 1.15
        if getattr(mem, "pinned", 0):
            score *= 1.2
        if memory_type == "compressed":
            score *= 0.9
        return min(max(score, 0.0), 1.0)

    def _keyword_score(self, query: str, scored: dict):
        keyword_results = self.db.search_memories(query, limit=10, tenant_id=self.tenant_id)
        for mem in keyword_results:
            if mem.id in scored:
                continue
            # 关键词命中给固定基础分，再叠加衰减/重要性
            importance = getattr(mem, "importance", 0.5) or 0.5
            score = decay_score(0.5, importance, 0)  # 假设 last_accessed=now
            score = self._adjust_score(score, mem)
            scored[mem.id] = (mem, score)
