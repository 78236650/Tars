"""知识库检索器 — 向量检索 + 关键词过滤"""
from typing import List, Dict, Any

from tars.reranker import CrossEncoderReranker
from tars.search.query_expansion import QueryExpander


class KnowledgeRetriever:
    """知识库检索器"""

    def __init__(
        self,
        vector_store,
        embedding_provider=None,
        query_expander: QueryExpander | None = None,
        reranker: CrossEncoderReranker | None = None,
        use_reranker: bool = True,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.query_expander = query_expander or QueryExpander(provider=None)
        self.reranker = reranker
        self.use_reranker = use_reranker

    def retrieve(
        self,
        query: str,
        collection_ids: List[str],
        top_k: int = 5,
        tenant_id: str = "default",
        expand: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        从指定知识库中检索相关内容
        返回: [{text, metadata, score, source}]
        """
        if not collection_ids:
            return []

        queries = self.query_expander.expand(query, method="synonym") if expand else [query]
        all_results: list[dict[str, Any]] = []
        for variant in queries:
            for collection_id in collection_ids:
                try:
                    results = self.vector_store.query(
                        query_text=variant,
                        top_k=max(top_k * 2, 10),
                        tenant_id=tenant_id,
                        collection_name=f"knowledge_{collection_id}",
                    )
                    for item in results:
                        all_results.append({
                            "id": item.get("id"),
                            "text": item["document"],
                            "metadata": item["metadata"],
                            "score": 1.0 - item["distance"],  # L2 距离转相似度
                            "source": {
                                "collection_id": collection_id,
                                "file_name": item["metadata"].get("file_name", ""),
                                "chunk_index": item["metadata"].get("chunk_index", 0),
                                "chunk_total": item["metadata"].get("chunk_total", 1),
                            },
                        })
                except Exception as e:
                    print(f"[KnowledgeRetriever] 检索失败 {collection_id}: {e}")
                    continue

        deduped: dict[str, dict[str, Any]] = {}
        for item in all_results:
            key = item.get("id") or f"{item['metadata'].get('doc_id', '')}:{item['source']['chunk_index']}:{item['text'][:50]}"
            if key not in deduped or item["score"] > deduped[key]["score"]:
                deduped[key] = item

        ranked = list(deduped.values())
        ranked.sort(key=lambda x: x["score"], reverse=True)
        candidates = ranked[: max(top_k * 4, 20)]
        if self.reranker and self.use_reranker:
            return self.reranker.rerank(query, candidates, top_k=top_k, text_key="text")
        return candidates[:top_k]

    def retrieve_with_context(
        self,
        query: str,
        collection_ids: List[str],
        top_k: int = 5,
        context_window: int = 1,
        tenant_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        检索并拼接上下文（相邻 chunk）
        context_window: 前后各取几个 chunk
        """
        base_results = self.retrieve(query, collection_ids, top_k, tenant_id)

        enriched = []
        for result in base_results:
            meta = result["metadata"]
            doc_id = meta.get("doc_id", "")
            collection_id = meta.get("collection_id", "")
            current_idx = meta.get("chunk_index", 0)
            total = meta.get("chunk_total", 1)

            # 获取相邻 chunk
            context_chunks = []
            for offset in range(-context_window, context_window + 1):
                idx = current_idx + offset
                if idx < 0 or idx >= total:
                    continue
                chunk_id = f"{doc_id}_chunk_{idx}"
                try:
                    chunk_data = self.vector_store.get_by_ids(
                        ids=[chunk_id],
                        tenant_id=tenant_id,
                        collection_name=f"knowledge_{collection_id}",
                    )
                    if chunk_data:
                        context_chunks.append(chunk_data[0]["document"])
                except Exception:
                    pass

            enriched.append({
                **result,
                "context_text": "\n".join(context_chunks),
            })

        return enriched
