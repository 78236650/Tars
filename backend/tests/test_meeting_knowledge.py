"""Meeting approve-to-knowledge uses org scope and SQLite index fallback."""
import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tars.context import set_request_context, clear_request_context
from tars.database import Database
from tars.knowledge.indexer import KnowledgeIndexer
from tars.knowledge.schema import ensure_knowledge_schema
from tars.memory.embeddings import DeterministicEmbeddingProvider
from tars.org import ORG_ID


class UnavailableVectorStore:
    @property
    def is_available(self):
        return False


@pytest.fixture
def meeting_db(tmp_path):
    db = Database(db_path=str(tmp_path / "meeting_kb.db"))
    ensure_knowledge_schema(db)
    conn = db._get_conn()
    cursor = conn.cursor()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    cursor.execute(
        "INSERT INTO transcriptions (id, user_id, file_path, file_name, transcript, summary, key_points, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "tx-1",
            "user-meeting-test",
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
    yield db
    db.close()
    clear_request_context()


def test_ensure_meeting_collection_org_scoped(meeting_db):
    from tars.api.meeting import _ensure_meeting_collection

    db = meeting_db
    cursor = db._get_conn().cursor()
    coll_id = _ensure_meeting_collection(cursor, ORG_ID)
    db._get_conn().commit()
    assert coll_id
    cursor.execute(
        "SELECT name, tenant_id FROM document_collections WHERE id = ?",
        (coll_id,),
    )
    row = cursor.fetchone()
    assert row[0] == "会议纪要"
    assert row[1] == ORG_ID


def test_index_meeting_summary_sqlite_fallback(meeting_db):
    db = meeting_db
    cursor = db._get_conn().cursor()
    from tars.api.meeting import _ensure_meeting_collection

    collection_id = _ensure_meeting_collection(cursor, ORG_ID)
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
        tenant_id=ORG_ID,
    )
    assert result["status"] == "indexed"
    assert result.get("backend") == "sqlite"


@pytest.mark.asyncio
async def test_approve_to_knowledge_uses_org_scope(meeting_db):
    db = meeting_db
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
    set_request_context(str(uuid.uuid4()))

    data = await approve_to_knowledge(
        "tx-1",
        ApproveToKnowledgeRequest(
            summary="讨论了知识库集成方案。",
            key_points=["集成知识库"],
        ),
    )
    clear_request_context()

    assert data["success"] is True
    assert data["collection_name"] == "会议纪要"

    cursor = db._get_conn().cursor()
    cursor.execute(
        "SELECT tenant_id, name FROM document_collections WHERE id = ?",
        (data["collection_id"],),
    )
    row = cursor.fetchone()
    assert row[0] == ORG_ID
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
        tenant_id=ORG_ID,
        collection_id=data["collection_id"],
    )
    assert hits
    assert "ref:" in text
    assert any("知识库" in (h.get("text") or "") for h in hits)
