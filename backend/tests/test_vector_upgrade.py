"""Tests for delete_document in KnowledgeIndexer"""
from unittest.mock import MagicMock
from tars.knowledge.indexer import KnowledgeIndexer


def _make_indexer(chunk_count=3):
    vector_store = MagicMock()
    db = MagicMock()
    db.get_document_file.return_value = {"id": "doc1", "chunk_count": chunk_count}
    db.delete_document_file.return_value = True
    return KnowledgeIndexer(vector_store=vector_store, embedding_provider=None, db=db), vector_store, db


def test_delete_document_calls_vector_store_delete():
    indexer, vector_store, db = _make_indexer(chunk_count=3)
    result = indexer.delete_document("doc1", "col1", "default")
    assert result is True
    vector_store.delete.assert_called_once_with(
        ids=["doc1_chunk_0", "doc1_chunk_1", "doc1_chunk_2"],
        tenant_id="default",
        collection_name="knowledge_col1",
    )


def test_delete_document_removes_db_record():
    indexer, vector_store, db = _make_indexer(chunk_count=2)
    indexer.delete_document("doc1", "col1")
    db.delete_document_file.assert_called_once_with("doc1")


def test_delete_document_no_chunks_skips_vector_delete():
    indexer, vector_store, db = _make_indexer(chunk_count=0)
    result = indexer.delete_document("doc1", "col1")
    assert result is True
    vector_store.delete.assert_not_called()


def test_delete_document_missing_doc_returns_false():
    indexer, vector_store, db = _make_indexer()
    db.get_document_file.return_value = None
    result = indexer.delete_document("missing", "col1")
    assert result is False
    vector_store.delete.assert_not_called()


def test_delete_document_no_db_returns_false():
    indexer = KnowledgeIndexer(vector_store=MagicMock(), embedding_provider=None, db=None)
    result = indexer.delete_document("doc1", "col1")
    assert result is False


# --- Reranker integration tests ---

from tars.memory.search import HybridSearch
from tars.search.gateway import SearchGateway


def _make_mem(id_, content, category="general"):
    m = MagicMock()
    m.id = id_
    m.content = content
    m.category = category
    m.importance = 0.5
    m.last_accessed = None
    return m


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
    """Reranker is called and its output is used."""
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


def test_search_gateway_reranks_knowledge_results():
    """SearchGateway passes knowledge results through reranker."""
    knowledge_retriever = MagicMock()
    knowledge_retriever.retrieve.return_value = [
        {"text": "doc A", "score": 0.6},
        {"text": "doc B", "score": 0.8},
    ]

    db = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [("col1",)]
    conn.cursor.return_value = cursor
    db._get_conn.return_value = conn

    reranker = MagicMock()
    reranker.rerank.return_value = [{"text": "doc B", "score": 0.8}]

    gw = SearchGateway(
        db=db,
        vector_store=None,
        embedding_provider=None,
        knowledge_retriever=knowledge_retriever,
        reranker=reranker,
        use_reranker=True,
    )
    # Disable expansion and cache for simplicity
    gw.expander = MagicMock()
    gw.expander.expand.return_value = ["query"]
    gw.cache = MagicMock()
    gw.cache.get.return_value = None

    result = gw.search("query", sources=["knowledge"], use_cache=False, use_expansion=False)

    reranker.rerank.assert_called_once()
    assert result["sources"]["knowledge"] == [{"text": "doc B", "score": 0.8}]


# --- DocumentParser tests ---

import pytest
import tempfile
import os
from tars.knowledge.parsers import DocumentParser, TextParser, MarkdownParser


def test_text_parser():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("hello world")
        path = f.name
    try:
        assert TextParser().parse(path) == "hello world"
    finally:
        os.unlink(path)


def test_markdown_parser_strips_syntax():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write("# Title\n- item\n**bold**\n[link](http://x.com)")
        path = f.name
    try:
        result = MarkdownParser().parse(path)
        assert "#" not in result
        assert "- " not in result
        assert "http://x.com" not in result
        assert "Title" in result
        assert "item" in result
    finally:
        os.unlink(path)


def test_document_parser_txt():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("test content")
        path = f.name
    try:
        assert DocumentParser().parse(path) == "test content"
    finally:
        os.unlink(path)


def test_document_parser_unsupported_extension():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        path = f.name
    try:
        with pytest.raises(ValueError, match="暂不支持"):
            DocumentParser().parse(path)
    finally:
        os.unlink(path)


def test_pdf_parser():
    fitz = pytest.importorskip("fitz")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "PDF content")
        doc.save(path)
        doc.close()
        result = DocumentParser().parse(path)
        assert "PDF content" in result
    finally:
        os.unlink(path)


def test_docx_parser():
    pytest.importorskip("docx")
    from docx import Document
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    try:
        doc = Document()
        doc.add_paragraph("DOCX content")
        doc.save(path)
        result = DocumentParser().parse(path)
        assert "DOCX content" in result
    finally:
        os.unlink(path)
