"""统一搜索网关 — 协调各路搜索"""
from typing import List, Dict, Any

from tars.reranker import CrossEncoderReranker
from .query_expansion import QueryExpander
from .cache import SearchCache


class SearchGateway:
    """统一搜索入口"""

    def __init__(
        self,
        db,
        vector_store,
        embedding_provider,
        provider=None,
        memory_search=None,
        knowledge_retriever=None,
        web_search_tool=None,
        reranker: CrossEncoderReranker | None = None,
        use_reranker: bool = True,
    ):
        self.db = db
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.provider = provider
        self.memory_search = memory_search
        self.knowledge_retriever = knowledge_retriever
        self.web_search_tool = web_search_tool
        self.reranker = reranker
        self.use_reranker = use_reranker

        self.expander = QueryExpander(provider)
        self.cache = SearchCache(db)

    def search(
        self,
        query: str,
        sources: List[str] = None,
        limit: int = 5,
        use_expansion: bool = True,
        use_cache: bool = True,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """
        统一搜索入口
        sources: ["memory", "knowledge", "web"]
        返回: {memory: [...], knowledge: [...], web: [...]}
        """
        if sources is None:
            sources = ["memory", "knowledge"]

        results = {"query": query, "sources": {}}

        # 查询扩展
        queries = [query]
        if use_expansion:
            queries = self.expander.expand(query, method="synonym")

        # 记忆搜索
        if "memory" in sources and self.memory_search:
            memory_results = []
            for q in queries:
                # 检查缓存
                cached = self.cache.get(q, "memory", limit) if use_cache else None
                if cached is not None:
                    memory_results.extend(cached)
                else:
                    try:
                        hits = self.memory_search.search(q, limit=limit)
                        formatted = [{"content": m.content, "category": m.category, "id": m.id} for m in hits]
                        if use_cache:
                            self.cache.set(q, formatted, "memory", limit, ttl_seconds=300)
                        memory_results.extend(formatted)
                    except Exception as e:
                        print(f"[SearchGateway] Memory search failed: {e}")

            # 去重
            seen = set()
            unique = []
            for r in memory_results:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique.append(r)
            if self.reranker and self.use_reranker and unique:
                unique = self.reranker.rerank(query, unique, top_k=limit, text_key="content")
            results["sources"]["memory"] = unique[:limit]

        # 知识库搜索
        if "knowledge" in sources and self.knowledge_retriever:
            knowledge_results = []
            for q in queries:
                cached = self.cache.get(q, "knowledge", limit) if use_cache else None
                if cached is not None:
                    knowledge_results.extend(cached)
                else:
                    try:
                        # 获取所有 collection
                        conn = self.db._get_conn()
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM document_collections WHERE tenant_id = ?",
                            (tenant_id,),
                        )
                        collection_ids = [r[0] for r in cursor.fetchall()]

                        if collection_ids:
                            hits = self.knowledge_retriever.retrieve(
                                q,
                                collection_ids,
                                top_k=limit,
                                tenant_id=tenant_id,
                                expand=False,
                            )
                            if use_cache:
                                self.cache.set(q, hits, "knowledge", limit, ttl_seconds=600)
                            knowledge_results.extend(hits)
                    except Exception as e:
                        print(f"[SearchGateway] Knowledge search failed: {e}")

            # 去重
            seen = set()
            unique = []
            for r in knowledge_results:
                key = r.get("text", "")[:50]
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
            if self.reranker and self.use_reranker and unique:
                unique = self.reranker.rerank(query, unique, top_k=limit, text_key="text")
            results["sources"]["knowledge"] = unique[:limit]

        return results
