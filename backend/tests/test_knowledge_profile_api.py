"""知识库 profile / 异步入库 API 单测。"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.api.knowledge import init_knowledge_api, router as knowledge_router
from tars.database import Database
from tars.knowledge.indexer import KnowledgeIndexer
from tars.knowledge.models import DocProfile, ParsedDocument
from tars.org import ORG_ID
from tars.knowledge.schema import ensure_knowledge_schema

from tests.conftest import setup_knowledge_auth


class _FakeEmbedding:
    def encode(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def knowledge_client(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    ensure_knowledge_schema(db)
    conn = db._get_conn()
    cur = conn.cursor()
    coll_id = "coll-1"
    cur.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (coll_id, ORG_ID, "test", "", "2026-05-24", "2026-05-24"),
    )
    conn.commit()

    app = FastAPI()
    app.include_router(knowledge_router)
    init_knowledge_api(db, vector_store=None, embedding_provider=_FakeEmbedding())
    auth_headers, _user = setup_knowledge_auth(db)

    with TestClient(app) as client:
        yield client, db, coll_id, tmp_path, auth_headers


def test_get_profile_not_found_returns_minimal(knowledge_client):
    client, db, coll_id, _, _headers = knowledge_client
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("d-none", coll_id, "x.txt", "/tmp/x.txt", ".txt", "ready", "2026-05-24"),
    )
    conn.commit()

    resp = client.get(
        f"/api/knowledge/collections/{coll_id}/documents/d-none/profile",
        headers=_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile_ready"] is False


def test_profile_crud_via_store(knowledge_client):
    client, db, coll_id, _, _headers = knowledge_client
    from tars.knowledge.profile_store import get_profile, save_profile

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, "
        "profile_ready, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("d1", coll_id, "制度.txt", "/tmp/x.txt", ".txt", "ready", 1, "2026-05-24"),
    )
    conn.commit()

    profile = DocProfile(
        doc_id="d1",
        doc_type="policy",
        title="制度",
        one_liner="一句话",
        summary="摘要内容",
        key_points=["要点A"],
    )
    save_profile(db, profile, tenant_id=ORG_ID, collection_id=coll_id)

    resp = client.get(
        f"/api/knowledge/collections/{coll_id}/documents/d1/profile",
        headers=_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "制度"
    assert data["key_points"] == ["要点A"]
    assert data["one_liner"] == "一句话"
    assert get_profile(db, "d1") is not None


@pytest.mark.asyncio
async def test_async_ingest_reaches_ready(knowledge_client):
    client, db, coll_id, tmp_path, _headers = knowledge_client
    from tars.api import knowledge as knowledge_api

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    file_path = str(uploads / "test_doc.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("这是测试制度文档。入库审批流程如下。")

    doc_id = "async-doc-1"
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, "
        "doc_type, profile_ready, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (doc_id, coll_id, "test_doc.txt", file_path, ".txt", "pending", "policy", 0, "2026-05-24"),
    )
    conn.commit()

    parsed = ParsedDocument(plain_text="这是测试制度文档。入库审批流程如下。")
    mock_profile = DocProfile(
        doc_id=doc_id,
        doc_type="policy",
        title="测试制度",
        one_liner="测试一句话",
        summary="测试摘要",
        key_points=["要点1"],
    )

    with patch("tars.knowledge.structure_parser.parse_to_document", return_value=parsed), patch(
        "tars.knowledge.enricher.enrich_document", return_value=mock_profile
    ):
        await knowledge_api._run_ingest(
            doc_id=doc_id,
            file_path=file_path,
            collection_id=coll_id,
            tenant_id=ORG_ID,
            doc_type="policy",
        )

    doc = db.get_document_file(doc_id)
    assert doc["status"] == "ready"
    assert doc["profile_ready"] is True
    assert doc["one_liner"] == "测试一句话"

    from tars.knowledge.profile_store import get_profile

    stored = get_profile(db, doc_id)
    assert stored is not None
    assert stored.summary == "测试摘要"


def test_document_status_endpoint(knowledge_client):
    client, db, coll_id, _, _headers = knowledge_client
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, "
        "profile_ready, one_liner, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("d2", coll_id, "a.txt", "/tmp/a.txt", ".txt", "enriching", 0, None, "2026-05-24"),
    )
    conn.commit()

    resp = client.get(
        f"/api/knowledge/collections/{coll_id}/documents/d2/status",
        headers=_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "enriching"
