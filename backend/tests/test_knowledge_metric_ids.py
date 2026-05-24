"""Tests for knowledge document metric_ids metadata."""
import json

import pytest

from tars.database import Database
from tars.knowledge.sqlite_store import get_document_metadata, search_docs_by_metric_id, set_document_metadata


@pytest.fixture
def db():
    d = Database(":memory:")
    conn = d._get_conn()
    conn.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll1", "default", "test", "", "2026-05-24", "2026-05-24"),
    )
    conn.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("doc1", "coll1", "gmv.md", "", "md", "indexed", "2026-05-24", "{}"),
    )
    conn.commit()
    return d


def test_set_and_get_document_metadata(db):
    set_document_metadata(db, "doc1", {"metric_ids": ["m-uuid-1", "m-uuid-2"]})
    meta = get_document_metadata(db, "doc1")
    assert meta["metric_ids"] == ["m-uuid-1", "m-uuid-2"]


def test_search_docs_by_metric_id_rejects_invalid_pattern(db):
    hits = search_docs_by_metric_id(db, "default", "%admin")
    assert hits == []


def test_search_docs_by_metric_id(db):
    set_document_metadata(db, "doc1", {"metric_ids": ["m-uuid-1"]})
    hits = search_docs_by_metric_id(db, "default", "m-uuid-1")
    assert len(hits) == 1
    assert hits[0]["source"]["doc_id"] == "doc1"
