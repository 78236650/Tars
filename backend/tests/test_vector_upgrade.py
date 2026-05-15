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
