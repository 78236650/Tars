"""Live-code tests retained after the knowledge module was removed (v5.0.5).

This file previously also covered KnowledgeIndexer / knowledge.parsers /
knowledge.retriever / api.knowledge batch upload — all deleted with the
knowledge package. Only the tests below exercise still-live code:
HybridSearch reranking, EmbeddingManager, and the Settings embedding API.
"""
from unittest.mock import MagicMock, patch

from tars.memory.search import HybridSearch


def _make_mem(id_, content, category="general"):
    m = MagicMock()
    m.id = id_
    m.content = content
    m.category = category
    m.importance = 0.5
    m.last_accessed = None
    return m


# --- HybridSearch reranker integration ---

def test_hybrid_search_without_reranker():
    """Backward compat: no reranker, returns sorted results."""
    mem = _make_mem("1", "hello world")
    db = MagicMock()
    db.search_memories.return_value = [mem]
    db.reinforce_memory.return_value = None
    hs = HybridSearch(db=db, tenant_id="default")
    results = hs.search("hello", limit=5)
    assert mem in results


def test_hybrid_search_calls_reranker_when_provided():
    """Reranker is called and its output ordering is used."""
    mem1 = _make_mem("1", "alpha")
    mem2 = _make_mem("2", "beta")
    db = MagicMock()
    db.search_memories.return_value = [mem1, mem2]
    db.reinforce_memory.return_value = None

    reranker = MagicMock()
    reranker.rerank.return_value = [
        {"text": "beta", "score": 0.9, "original": mem2},
        {"text": "alpha", "score": 0.5, "original": mem1},
    ]

    hs = HybridSearch(db=db, tenant_id="default", reranker=reranker)
    results = hs.search("query", limit=5)

    reranker.rerank.assert_called_once()
    assert results[0] is mem2
    assert results[1] is mem1
