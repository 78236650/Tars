"""SQLite BLOB fallback for knowledge chunks when Chroma is unavailable."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from tars.memory.deduplicator import cosine_similarity
from tars.memory.embeddings import deserialize_vector, serialize_vector


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def ensure_knowledge_chunks_table(db) -> None:
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_total INTEGER NOT NULL,
            file_name TEXT DEFAULT '',
            content TEXT NOT NULL,
            embedding BLOB,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_kchunks_coll_tenant ON knowledge_chunks(collection_id, tenant_id)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kchunks_doc ON knowledge_chunks(doc_id)")
    conn.commit()


def store_chunks(
    db,
    embedding_provider,
    *,
    chunks: List[Dict[str, Any]],
    doc_id: str,
    collection_id: str,
    tenant_id: str,
    file_name: str = "",
) -> int:
    """Persist chunk text + embeddings to SQLite. Returns stored count."""
    if not chunks:
        return 0
    ensure_knowledge_chunks_table(db)
    delete_chunks(db, doc_id)

    prefix = f"[{file_name}] " if file_name else ""
    documents = [prefix + c["text"] for c in chunks]
    embeddings = None
    if embedding_provider:
        try:
            embeddings = embedding_provider.encode(documents)
        except Exception as e:
            print(f"[KnowledgeSQLite] Embedding failed: {e}")

    conn = db._get_conn()
    cursor = conn.cursor()
    now = _now()
    stored = 0
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{chunk['chunk_index']}"
        emb_blob = None
        if embeddings and i < len(embeddings):
            emb_blob = serialize_vector(embeddings[i])
        cursor.execute(
            """
            INSERT INTO knowledge_chunks
            (id, collection_id, tenant_id, doc_id, chunk_index, chunk_total, file_name, content, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                collection_id,
                tenant_id,
                doc_id,
                chunk["chunk_index"],
                chunk.get("chunk_total", len(chunks)),
                file_name,
                chunk["text"],
                emb_blob,
                now,
            ),
        )
        stored += 1
    conn.commit()
    return stored


def delete_chunks(db, doc_id: str) -> None:
    ensure_knowledge_chunks_table(db)
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
    conn.commit()


def search_chunks(
    db,
    embedding_provider,
    query: str,
    collection_ids: List[str],
    tenant_id: str = "default",
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Semantic + keyword fallback search over SQLite knowledge chunks."""
    ensure_knowledge_chunks_table(db)
    if not collection_ids:
        return []

    conn = db._get_conn()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(collection_ids))
    cursor.execute(
        f"""
        SELECT id, content, file_name, chunk_index, chunk_total, collection_id, embedding
        FROM knowledge_chunks
        WHERE tenant_id = ? AND collection_id IN ({placeholders})
        """,
        [tenant_id, *collection_ids],
    )
    rows = cursor.fetchall()
    if not rows:
        return []

    scored: List[tuple[float, Dict[str, Any]]] = []
    query_lower = query.lower()
    query_tokens = [t for t in re.split(r"\s+", query_lower) if len(t) >= 2]

    query_vec = None
    if embedding_provider:
        try:
            query_vec = embedding_provider.encode([query])[0]
        except Exception as e:
            print(f"[KnowledgeSQLite] Query embedding failed: {e}")

    for row in rows:
        chunk_id, content, file_name, chunk_index, chunk_total, collection_id, emb_blob = row
        score = 0.0
        if query_vec and emb_blob:
            vec = deserialize_vector(emb_blob)
            if vec:
                score = max(score, cosine_similarity(query_vec, vec))
        if query_lower in (content or "").lower():
            score = max(score, 0.55)
        for token in query_tokens:
            if token in (content or "").lower():
                score = max(score, 0.45)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "id": chunk_id,
                    "text": content,
                    "metadata": {
                        "doc_id": chunk_id.rsplit("_chunk_", 1)[0],
                        "file_name": file_name,
                        "chunk_index": chunk_index,
                        "chunk_total": chunk_total,
                    },
                    "score": score,
                    "source": {
                        "collection_id": collection_id,
                        "file_name": file_name,
                        "chunk_index": chunk_index,
                        "chunk_total": chunk_total,
                    },
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def set_document_metadata(db, doc_id: str, metadata: Dict[str, Any]) -> None:
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE document_files SET metadata_json = ? WHERE id = ?",
        (json.dumps(metadata, ensure_ascii=False), doc_id),
    )
    conn.commit()


def get_document_metadata(db, doc_id: str) -> Dict[str, Any]:
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT metadata_json FROM document_files WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return {}


def search_docs_by_metric_id(
    db,
    tenant_id: str,
    metric_id: str,
    *,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    import logging
    import re

    logger = logging.getLogger(__name__)
    if not metric_id or not re.fullmatch(r"[A-Za-z0-9_-]+", metric_id):
        logger.warning("Invalid metric_id rejected: %r", metric_id)
        return []

    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT df.id, df.file_name, df.metadata_json
        FROM document_files df
        JOIN document_collections dc ON dc.id = df.collection_id
        WHERE dc.tenant_id = ? AND df.metadata_json LIKE ? ESCAPE '\\'
        LIMIT ?
        """,
        (tenant_id, f"%{metric_id.replace('%', '\\%').replace('_', '\\_')}%", top_k),
    )
    hits: List[Dict[str, Any]] = []
    for doc_id, file_name, meta_json in cursor.fetchall():
        meta: Dict[str, Any] = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except (json.JSONDecodeError, TypeError):
                pass
        metric_ids = meta.get("metric_ids") or []
        if metric_id not in metric_ids and metric_id not in (meta_json or ""):
            continue
        hits.append(
            {
                "id": doc_id,
                "text": file_name or "",
                "score": 0.6,
                "source": {"file_name": file_name or doc_id, "doc_id": doc_id},
                "metadata": {"doc_id": doc_id, "file_name": file_name},
            }
        )
    return hits
