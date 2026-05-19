"""Meeting approve-to-knowledge uses caller tenant and SQLite index fallback."""
import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tars.database import Database
from tars.knowledge.indexer import KnowledgeIndexer
from tars.memory.embeddings import DeterministicEmbeddingProvider


class UnavailableVectorStore:
    @property
    def is_available(self):
        return False


@pytest.fixture
def meeting_db(tmp_path):
    db = Database(db_path=str(tmp_path / "meeting_kb.db"))
    conn = db._get_conn()
    cursor = conn.cursor()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    tid = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO transcriptions (id, file_path, file_name, transcript, summary, key_points, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "tx-1",
            "/tmp/周会录音.mp3",
            "周会录音.mp3",
            "今天我们讨论了知识库与会议助手的集成方案。",
            "讨论了知识库集成。",
            json.dumps(["集成知识库"], ensure_ascii=False),
            "completed",
            now,
        ),
    )
    conn.commit()
    yield db, tid
    db.close()


def test_ensure_meeting_collection_per_tenant(meeting_db):
    from tars.api.meeting import _ensure_meeting_collection

    db, tenant_id = meeting_db
    cursor = db._get_conn().cursor()
    coll_id = _ensure_meeting_collection(cursor, tenant_id)
    db._get_conn().commit()
    assert coll_id
    cursor.execute(
        "SELECT name, tenant_id FROM document_collections WHERE id = ?",
        (coll_id,),
    )
    row = cursor.fetchone()
    assert row[0] == "会议纪要"
    assert row[1] == tenant_id


def test_index_meeting_summary_sqlite_fallback(meeting_db):
    db, tenant_id = meeting_db
    cursor = db._get_conn().cursor()
    from tars.api.meeting import _ensure_meeting_collection

    collection_id = _ensure_meeting_collection(cursor, tenant_id)
    db._get_conn().commit()

    indexer = KnowledgeIndexer(
        UnavailableVectorStore(),
        DeterministicEmbeddingProvider(dim=64),
        db=db,
    )
    result = indexer.index_document(
        text="[会议] 周会\n\n讨论了知识库集成。",
        doc_id="doc_meeting_summary",
        collection_id=collection_id,
        file_name="周会纪要",
        tenant_id=tenant_id,
    )
    assert result["status"] == "indexed"
    assert result.get("backend") == "sqlite"


@pytest.mark.asyncio
async def test_approve_to_knowledge_uses_tenant_header(meeting_db):
    db, tenant_id = meeting_db
    from tars.api.meeting import (
        ApproveToKnowledgeRequest,
        approve_to_knowledge,
        init_meeting_api,
    )

    class VS:
        @property
        def is_available(self):
            return False

    init_meeting_api(db, None, VS(), DeterministicEmbeddingProvider(dim=64))

    data = await approve_to_knowledge(
        "tx-1",
        ApproveToKnowledgeRequest(
            summary="讨论了知识库集成方案。",
            key_points=["集成知识库"],
        ),
        x_tenant_id=tenant_id,
    )
    assert data["success"] is True
    assert data["collection_name"] == "会议纪要"

    cursor = db._get_conn().cursor()
    cursor.execute(
        "SELECT tenant_id, name FROM document_collections WHERE id = ?",
        (data["collection_id"],),
    )
    row = cursor.fetchone()
    assert row[0] == tenant_id
    assert row[1] in ("会议纪要", "meeting_notes_kb")

    cursor.execute(
        "SELECT knowledge_doc_id, approved_at FROM transcriptions WHERE id = ?",
        ("tx-1",),
    )
    tx_row = cursor.fetchone()
    assert tx_row[0]
    assert tx_row[1]

    from tars.knowledge.access import search_knowledge

    class Retriever:
        vector_store = None

        def __init__(self):
            self.embedding_provider = DeterministicEmbeddingProvider(dim=64)

        def retrieve(self, **kwargs):
            return []

    text, hits = search_knowledge(
        db,
        Retriever(),
        "知识库集成",
        tenant_id=tenant_id,
        collection_id=data["collection_id"],
    )
    assert hits
    assert "ref:" in text
    assert any("知识库" in (h.get("text") or "") for h in hits)
