"""TARS v5.0 Phase 2 T2.5 — org-scoped knowledge base pool."""

import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.api.knowledge import init_knowledge_api, router as knowledge_router
from tars.context import clear_request_context, set_request_context
from tars.database import Database
from tars.knowledge.access import list_collection_targets, search_knowledge
from tars.knowledge.indexer import KnowledgeIndexer
from tars.memory.embeddings import DeterministicEmbeddingProvider
from tars.memory.turn_knowledge_publisher import ensure_chat_knowledge_collection
from tars.org import ORG_ID
from tars.knowledge.schema import ensure_knowledge_schema

from tests.conftest import setup_knowledge_auth


class UnavailableVectorStore:
    @property
    def is_available(self):
        return False


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "knowledge_org_scope.db"))
    ensure_knowledge_schema(database)
    yield database
    database.close()
    clear_request_context()


@pytest.fixture
def kb_client(db):
    app = FastAPI()
    app.include_router(knowledge_router)
    init_knowledge_api(
        db,
        vector_store=UnavailableVectorStore(),
        embedding_provider=DeterministicEmbeddingProvider(dim=64),
    )
    headers_a, user_a = setup_knowledge_auth(db)
    headers_b, user_b = setup_knowledge_auth(db)
    with TestClient(app) as client:
        yield client, db, headers_a, headers_b, user_a, user_b


def test_list_collection_targets_org_pool_only(db):
    conn = db._get_conn()
    cursor = conn.cursor()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-org", ORG_ID, "Org KB", "", now, now),
    )
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-legacy", "default", "Legacy KB", "", now, now),
    )
    conn.commit()

    targets = list_collection_targets(db, ORG_ID)
    assert targets == [("coll-org", ORG_ID)]


def test_list_collections_includes_legacy_user_tenant(kb_client):
    client, db, headers_a, headers_b, user_a, user_b = kb_client
    conn = db._get_conn()
    cursor = conn.cursor()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-a-legacy", user_a.id, "User A Legacy", "", now, now),
    )
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("coll-b-legacy", user_b.id, "User B Legacy", "", now, now),
    )
    conn.commit()

    listed_a = client.get("/api/knowledge/collections", headers=headers_a)
    ids_a = {c["id"] for c in listed_a.json()["collections"]}
    assert "coll-a-legacy" in ids_a
    assert "coll-b-legacy" not in ids_a

    listed_b = client.get("/api/knowledge/collections", headers=headers_b)
    ids_b = {c["id"] for c in listed_b.json()["collections"]}
    assert "coll-b-legacy" in ids_b
    assert "coll-a-legacy" not in ids_b


def test_user_a_creates_collection_user_b_lists(kb_client):
    client, db, headers_a, headers_b, _, _ = kb_client

    create = client.post(
        "/api/knowledge/collections",
        json={"name": "Shared Org KB", "description": "team docs"},
        headers=headers_a,
    )
    assert create.status_code == 200
    coll_id = create.json()["collection"]["id"]

    cursor = db._get_conn().cursor()
    cursor.execute(
        "SELECT tenant_id FROM document_collections WHERE id = ?",
        (coll_id,),
    )
    assert cursor.fetchone()[0] == ORG_ID

    listed = client.get("/api/knowledge/collections", headers=headers_b)
    assert listed.status_code == 200
    ids = {c["id"] for c in listed.json()["collections"]}
    assert coll_id in ids


def test_user_b_searches_user_a_indexed_doc(kb_client):
    client, db, headers_a, headers_b, _, _ = kb_client

    create = client.post(
        "/api/knowledge/collections",
        json={"name": "Search Pool"},
        headers=headers_a,
    )
    coll_id = create.json()["collection"]["id"]

    set_request_context("user-a")
    indexer = KnowledgeIndexer(
        UnavailableVectorStore(),
        DeterministicEmbeddingProvider(dim=64),
        db=db,
    )
    doc_id = str(uuid.uuid4())
    result = indexer.index_document(
        text="Org-wide deployment runbook for TARS v5 knowledge pool.",
        doc_id=doc_id,
        collection_id=coll_id,
        file_name="runbook.md",
        tenant_id=ORG_ID,
    )
    assert result["status"] == "indexed"
    clear_request_context()

    set_request_context("user-b")

    class Retriever:
        vector_store = None

        def __init__(self):
            self.embedding_provider = DeterministicEmbeddingProvider(dim=64)

        def retrieve(self, **kwargs):
            return []

    _, hits = search_knowledge(
        db,
        Retriever(),
        "deployment runbook",
        tenant_id=ORG_ID,
        collection_id=coll_id,
    )
    clear_request_context()

    assert hits
    assert any("runbook" in (h.get("text") or "").lower() for h in hits)

    query = client.post(
        f"/api/knowledge/collections/{coll_id}/query",
        json={"query": "deployment runbook", "top_k": 5},
        headers=headers_b,
    )
    assert query.status_code == 200
    assert query.json()["total"] >= 1


def test_ensure_chat_collection_is_org_scoped(db):
    set_request_context("user-a")
    coll_a = ensure_chat_knowledge_collection(db, ORG_ID)
    clear_request_context()

    set_request_context("user-b")
    coll_b = ensure_chat_knowledge_collection(db, ORG_ID)
    clear_request_context()

    assert coll_a == coll_b

    cursor = db._get_conn().cursor()
    cursor.execute(
        "SELECT tenant_id FROM document_collections WHERE id = ?",
        (coll_a,),
    )
    assert cursor.fetchone()[0] == ORG_ID


def test_mutating_routes_require_auth(db, tmp_path):
    app = FastAPI()
    app.include_router(knowledge_router)
    init_knowledge_api(db, vector_store=None, embedding_provider=MagicMock())
    with TestClient(app) as client:
        resp = client.post("/api/knowledge/collections", json={"name": "no auth"})
        assert resp.status_code == 401
