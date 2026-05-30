"""将「记住要点」合成一篇知识库文档。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional


from ..org import ORG_ID


CHAT_KB_NAME = "对话精华"
CHAT_KB_DESCRIPTION = "从聊天记忆中升格合成的技术笔记（非碎片直写）"


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def ensure_chat_knowledge_collection(db, tenant_id: str = ORG_ID) -> str:
    from ..knowledge.schema import ensure_knowledge_schema

    ensure_knowledge_schema(db)
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM document_collections WHERE name = ? AND tenant_id = ?",
        (CHAT_KB_NAME, tenant_id),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    collection_id = str(uuid.uuid4())
    now = _now()
    cursor.execute(
        """
        INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (collection_id, tenant_id, CHAT_KB_NAME, CHAT_KB_DESCRIPTION, now, now),
    )
    conn.commit()
    return collection_id


def publish_synthesized_note(
    *,
    db,
    vector_store,
    embedding_provider,
    tenant_id: str = ORG_ID,
    title: str,
    markdown: str,
    source_memory_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """索引一篇合成笔记到知识库，返回 doc_id。"""
    text = (markdown or "").strip()
    if not text or db is None or embedding_provider is None:
        return None

    from ..knowledge.indexer import KnowledgeIndexer

    collection_id = ensure_chat_knowledge_collection(db, tenant_id)
    doc_id = str(uuid.uuid4())
    doc_title = title.strip() or f"对话精华({datetime.now().strftime('%Y-%m-%d')})"

    if source_memory_ids:
        footer = "\n\n---\n来源记忆 ID: " + ", ".join(source_memory_ids[:20])
        text = text + footer

    indexer = KnowledgeIndexer(vector_store, embedding_provider, db=db)
    result = indexer.index_document(
        text=text,
        doc_id=doc_id,
        collection_id=collection_id,
        file_name=doc_title,
        file_type="chat_remember",
        tenant_id=tenant_id,
    )
    if not (result.get("chunk_count", 0) > 0 or result.get("status") == "indexed"):
        return None

    conn = db._get_conn()
    cursor = conn.cursor()
    now = _now()
    cursor.execute(
        """
        INSERT INTO document_files
        (id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            collection_id,
            doc_title,
            "",
            "chat_remember",
            int(result.get("chunk_count") or 0),
            "indexed",
            now,
        ),
    )
    conn.commit()
    return doc_id
