"""Task 12: 上传 doc_type override 与集合 default_doc_type。"""
import io
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.api.knowledge import init_knowledge_api, resolve_upload_doc_type, router as knowledge_router
from tars.database import Database


class _FakeEmbedding:
    def encode(self, texts):
        return [[0.1, 0.2] for _ in texts]


@pytest.fixture
def kb_client(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    app = FastAPI()
    app.include_router(knowledge_router)
    init_knowledge_api(db, vector_store=None, embedding_provider=_FakeEmbedding())
    with TestClient(app) as client:
        yield client, db


def test_resolve_upload_doc_type_priority():
    assert resolve_upload_doc_type("proposal", "policy") == ("proposal", "proposal")
    assert resolve_upload_doc_type(None, "policy") == ("policy", "policy")
    assert resolve_upload_doc_type(None, None) == (None, "generic")
    assert resolve_upload_doc_type("", "metrics") == ("metrics", "metrics")


def test_create_collection_with_default_doc_type(kb_client):
    client, _db = kb_client
    resp = client.post(
        "/api/knowledge/collections",
        json={"name": "制度库", "description": "test", "default_doc_type": "policy"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["collection"]["default_doc_type"] == "policy"


def test_upload_inherits_collection_default_doc_type(kb_client, tmp_path):
    client, db = kb_client
    coll = client.post(
        "/api/knowledge/collections",
        json={"name": "c", "default_doc_type": "policy"},
    ).json()["collection"]["id"]

    content = b"test content for policy doc"
    resp = client.post(
        f"/api/knowledge/collections/{coll}/documents",
        files={"file": ("note.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document"]["doc_type"] == "policy"
    assert body["document"]["doc_type_source"] == "collection_default"

    doc_id = body["document"]["id"]
    row = db.get_document_file(doc_id)
    assert row["doc_type"] == "policy"


def test_upload_doc_type_override(kb_client):
    client, db = kb_client
    coll = client.post(
        "/api/knowledge/collections",
        json={"name": "c2", "default_doc_type": "policy"},
    ).json()["collection"]["id"]

    resp = client.post(
        f"/api/knowledge/collections/{coll}/documents",
        files={"file": ("data.xlsx", io.BytesIO(b"dummy"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"doc_type": "metrics"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document"]["doc_type"] == "metrics"
    assert body["document"]["doc_type_source"] == "override"


@pytest.mark.asyncio
async def test_auto_infer_doc_type_from_filename(kb_client, tmp_path):
    client, db = kb_client
    coll = client.post("/api/knowledge/collections", json={"name": "auto"}).json()["collection"]["id"]

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    file_path = uploads / "test_doc_制度管理办法.txt"
    file_path.write_text("制度正文", encoding="utf-8")
    doc_id = "doc-auto-1"
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, doc_type, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (doc_id, coll, "制度管理办法.txt", str(file_path), ".txt", "pending", "generic", "2026-05-24"),
    )
    conn.commit()

    from tars.api import knowledge as knowledge_api
    from tars.knowledge.models import ParsedDocument

    parsed = ParsedDocument(plain_text="制度正文", doc_type_hint="policy")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("tars.knowledge.structure_parser.parse_to_document", lambda fp, dt: parsed)
        mp.setattr("tars.knowledge.enricher.enrich_document", lambda *a, **k: None)
        await knowledge_api._run_ingest(
            doc_id=doc_id,
            file_path=str(file_path),
            collection_id=coll,
            tenant_id="default",
            doc_type=None,
        )

    row = db.get_document_file(doc_id)
    assert row["doc_type"] == "policy"
