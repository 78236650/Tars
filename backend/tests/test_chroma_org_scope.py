"""TARS v5.0 Phase 2 Task T2.2 — org-scoped Chroma memory collections."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.context import clear_request_context, set_request_context
from tars.org import ORG_ID
from tars.vectorstore.scope import (
    collection_full_name,
    memory_chroma_metadata,
    memory_visibility_filter,
)
from tars.vectorstore.chroma_client import ChromaVectorStore


def test_collection_full_name_uses_org_id():
    assert collection_full_name("memories") == f"memories_{ORG_ID}"
    assert collection_full_name("memories", "user-a") == f"memories_{ORG_ID}"
    assert collection_full_name("knowledge_coll1", "legacy_tenant") == f"knowledge_coll1_{ORG_ID}"


def test_memory_visibility_filter_private_vs_shared():
    filt_a = memory_visibility_filter("user-a")
    assert filt_a == {"$or": [{"scope": "shared"}, {"user_id": "user-a"}]}

    filt_none = memory_visibility_filter(None)
    assert filt_none == {"$or": [{"scope": "shared"}, {"user_id": ""}]}


def test_memory_chroma_metadata_shared_uses_empty_user_id():
    meta = memory_chroma_metadata("shared", None, category="fact")
    assert meta["scope"] == "shared"
    assert meta["user_id"] == ""
    assert meta["category"] == "fact"


@pytest.fixture
def chroma_available():
    try:
        import chromadb  # noqa: F401
    except ImportError:
        pytest.skip("chromadb not installed")
    return True


@pytest.fixture
def org_chroma_store(tmp_path, chroma_available):
    vs = ChromaVectorStore(persist_directory=str(tmp_path / "chroma"))
    if not vs.is_available:
        pytest.skip("Chroma client not available")
    return vs


def test_user_a_shared_memory_visible_to_user_b(org_chroma_store):
    """A writes shared doc; B semantic query with visibility filter can recall it."""
    doc = "Org-wide quarterly revenue target is 10M"
    meta = memory_chroma_metadata("shared", None, category="fact", importance=0.8, source="test")
    doc_id = "shared-mem-1"

    org_chroma_store.add_documents(
        documents=[doc],
        metadatas=[meta],
        ids=[doc_id],
        tenant_id=ORG_ID,
        collection_name="memories",
    )

    set_request_context("user-b")
    try:
        results = org_chroma_store.query(
            query_text="quarterly revenue",
            top_k=5,
            tenant_id=ORG_ID,
            collection_name="memories",
            filter_dict=memory_visibility_filter("user-b"),
        )
    finally:
        clear_request_context()

    assert any(r["id"] == doc_id for r in results)


def test_user_a_private_memory_not_visible_to_user_b(org_chroma_store):
    doc = "User A secret passphrase is alpha-beta-gamma"
    meta = memory_chroma_metadata("private", "user-a", category="fact", importance=0.9, source="test")
    doc_id = "private-mem-a"

    org_chroma_store.add_documents(
        documents=[doc],
        metadatas=[meta],
        ids=[doc_id],
        tenant_id=ORG_ID,
        collection_name="memories",
    )

    set_request_context("user-b")
    try:
        results = org_chroma_store.query(
            query_text="secret passphrase",
            top_k=5,
            tenant_id=ORG_ID,
            collection_name="memories",
            filter_dict=memory_visibility_filter("user-b"),
        )
    finally:
        clear_request_context()

    assert not any(r["id"] == doc_id for r in results)


def test_collection_name_is_org_scoped(org_chroma_store):
    coll = org_chroma_store.get_collection(collection_name="memories", tenant_id="user-legacy")
    assert coll.name == f"memories_{ORG_ID}"
