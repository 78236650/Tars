"""Shared knowledge-base access for API, tools, and agent injection."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def list_collection_targets(
    db,
    tenant_id: str,
    collection_id: Optional[str] = None,
    include_shared_default: bool = True,
) -> List[Tuple[str, str]]:
    """
    Return (collection_id, owner_tenant_id) pairs for search.
    Vectors are stored under owner_tenant_id in Chroma (knowledge_{id}_{tenant}).
    """
    if collection_id:
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tenant_id FROM document_collections WHERE id = ?",
            (collection_id,),
        )
        row = cursor.fetchone()
        if not row:
            return []
        return [(row[0], row[1])]

    conn = db._get_conn()
    cursor = conn.cursor()
    targets: List[Tuple[str, str]] = []
    seen: set[str] = set()

    cursor.execute(
        "SELECT id, tenant_id FROM document_collections WHERE tenant_id = ?",
        (tenant_id,),
    )
    for coll_id, owner in cursor.fetchall():
        targets.append((coll_id, owner))
        seen.add(coll_id)

    if include_shared_default and tenant_id != "default":
        cursor.execute(
            "SELECT id, tenant_id FROM document_collections WHERE tenant_id = ?",
            ("default",),
        )
        for coll_id, owner in cursor.fetchall():
            if coll_id not in seen:
                targets.append((coll_id, owner))
                seen.add(coll_id)

    return targets


def search_knowledge(
    db,
    retriever,
    query: str,
    tenant_id: str = "default",
    collection_id: Optional[str] = None,
    top_k: int = 5,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Search all relevant collections with correct per-collection tenant_id.
    Returns (formatted_text_for_prompt, raw_results).
    """
    if not query or not query.strip():
        return "", []
    if retriever is None or db is None:
        return "", []

    targets = list_collection_targets(db, tenant_id, collection_id=collection_id)
    if not targets:
        return "（当前账号下暂无知识库文档）", []

    all_results: List[Dict[str, Any]] = []
    per_coll_k = max(3, top_k // max(len(targets), 1))

    chroma_ok = bool(
        retriever.vector_store and getattr(retriever.vector_store, "is_available", False)
    )

    for coll_id, owner_tenant in targets:
        hits: list[dict[str, Any]] = []
        if chroma_ok:
            try:
                hits = retriever.retrieve(
                    query=query,
                    collection_ids=[coll_id],
                    top_k=per_coll_k,
                    tenant_id=owner_tenant,
                    expand=False,
                )
            except Exception as e:
                print(f"[KnowledgeAccess] Chroma 检索失败 {coll_id}@{owner_tenant}: {e}")

        if not hits and db is not None:
            try:
                from .sqlite_store import search_chunks

                hits = search_chunks(
                    db,
                    retriever.embedding_provider,
                    query=query,
                    collection_ids=[coll_id],
                    tenant_id=owner_tenant,
                    top_k=per_coll_k,
                )
            except Exception as e:
                print(f"[KnowledgeAccess] SQLite 检索失败 {coll_id}@{owner_tenant}: {e}")

        all_results.extend(hits)

    if not all_results:
        return "（知识库中未找到与问题相关的内容）", []

    deduped: dict[str, Dict[str, Any]] = {}
    for item in all_results:
        key = item.get("id") or f"{item.get('source', {}).get('file_name', '')}:{item.get('text', '')[:80]}"
        if key not in deduped or item.get("score", 0) > deduped[key].get("score", 0):
            deduped[key] = item

    ranked = sorted(deduped.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]
    lines = [f"共检索到 {len(ranked)} 条知识库片段（请在回答中引用来源）："]
    for i, r in enumerate(ranked, 1):
        source = r.get("source", {})
        file_name = source.get("file_name", "未知文件")
        text = (r.get("text") or "").strip()
        snippet = text[:500] + ("..." if len(text) > 500 else "")
        lines.append(f"\n[{i}] 来源: {file_name}\n{snippet}")

    return "\n".join(lines), ranked
