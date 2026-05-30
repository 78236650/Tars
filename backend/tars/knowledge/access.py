"""Shared knowledge-base access for API, tools, and agent injection."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from tars.org import ORG_ID

BROWSE_CHUNK_TYPES = frozenset({"doc_summary", "section_summary", "key_fact"})
BROWSE_TYPE_BOOST = {
    "doc_summary": 0.15,
    "section_summary": 0.10,
    "key_fact": 0.08,
}


def _derive_doc_id(hit: Dict[str, Any]) -> str:
    source = hit.get("source", {}) or {}
    meta = hit.get("metadata", {}) or {}
    chunk_id = hit.get("id") or ""
    doc_id = meta.get("doc_id") or source.get("doc_id")
    if doc_id:
        return str(doc_id)
    if chunk_id and "_chunk_" in chunk_id:
        return chunk_id.rsplit("_chunk_", 1)[0]
    for sep in ("_summary_", "_section_", "_keyfact_", "_qa_", "_glossary_"):
        if sep in chunk_id:
            return chunk_id.split(sep)[0]
    return chunk_id or "unknown"


def _chunk_type(hit: Dict[str, Any]) -> str:
    meta = hit.get("metadata", {}) or {}
    ct = meta.get("chunk_type")
    if ct:
        return str(ct)
    chunk_id = hit.get("id") or ""
    if "_summary_" in chunk_id:
        return "doc_summary"
    if "_section_" in chunk_id:
        return "section_summary"
    if "_keyfact_" in chunk_id:
        return "key_fact"
    return "passage"


def _derive_source_type(doc_id: str, file_name: str) -> str:
    lowered = f"{doc_id} {file_name}".lower()
    if "meeting" in lowered or "会议" in file_name:
        return "meeting"
    return "document"


def enrich_hit(hit: Dict[str, Any], *, db=None, tenant_id: str = ORG_ID) -> Dict[str, Any]:
    """Add citation fields used by agent prompt and frontend [ref:doc_id] cards."""
    source = dict(hit.get("source", {}) or {})
    meta = dict(hit.get("metadata", {}) or {})
    doc_id = _derive_doc_id(hit)
    file_name = source.get("file_name") or meta.get("file_name") or "未知文档"
    source_type = _derive_source_type(doc_id, file_name)
    chunk_type = _chunk_type(hit)

    one_liner = None
    if db is not None and doc_id and doc_id != "unknown":
        try:
            from .profile_store import get_profile

            profile = get_profile(db, doc_id)
            if profile:
                one_liner = profile.one_liner
        except Exception:
            pass

    citation = {
        "doc_id": doc_id,
        "doc_title": file_name,
        "source": source_type,
        "collection_id": source.get("collection_id") or meta.get("collection_id"),
        "chunk_index": source.get("chunk_index", meta.get("chunk_index")),
        "chunk_type": chunk_type,
        "one_liner": one_liner,
    }
    source.update({"doc_id": doc_id, "source_type": source_type, "chunk_type": chunk_type})
    meta.update(citation)

    enriched = dict(hit)
    enriched["source"] = source
    enriched["metadata"] = meta
    enriched["citation"] = citation
    enriched["chunk_type"] = chunk_type
    return enriched


def format_citation_results(ranked: List[Dict[str, Any]]) -> str:
    lines = [
        "共检索到 {n} 条知识库片段（引用时在句末标注 [ref:doc_id|文档标题]）：".format(n=len(ranked))
    ]
    for i, r in enumerate(ranked, 1):
        cite = r.get("citation") or {}
        doc_id = cite.get("doc_id")
        doc_title = cite.get("doc_title") or "未知文档"
        source_type = cite.get("source") or "document"
        one_liner = cite.get("one_liner")
        text = (r.get("text") or "").strip()
        snippet = text[:500] + ("..." if len(text) > 500 else "")
        if doc_id and doc_id != "unknown":
            header = f"\n[{i}] ref:{doc_id} 来源: {doc_title} ({source_type})"
        else:
            header = f"\n[{i}] 来源: {doc_title} ({source_type})"
        if one_liner:
            header += f"\n    摘要: {one_liner}"
        lines.append(f"{header}\n{snippet}")
    return "\n".join(lines)


def list_collection_targets(
    db,
    tenant_id: str | None = None,
    collection_id: Optional[str] = None,
    include_shared_default: bool = True,
) -> List[Tuple[str, str]]:
    """
    Return (collection_id, org_id) pairs for search within the org knowledge pool.
    Vectors are stored under org scope in Chroma (``knowledge_{id}_{ORG_ID}``).
    """
    del include_shared_default
    org_id = tenant_id or ORG_ID

    if collection_id:
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tenant_id FROM document_collections WHERE id = ? AND tenant_id = ?",
            (collection_id, org_id),
        )
        row = cursor.fetchone()
        if not row:
            return []
        return [(row[0], row[1])]

    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, tenant_id FROM document_collections WHERE tenant_id = ?",
        (org_id,),
    )
    return [(coll_id, owner) for coll_id, owner in cursor.fetchall()]


def _apply_browse_filter(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []
    for item in results:
        ct = _chunk_type(item)
        if ct in BROWSE_CHUNK_TYPES:
            boosted = dict(item)
            boosted["score"] = float(item.get("score", 0)) + BROWSE_TYPE_BOOST.get(ct, 0)
            filtered.append(boosted)
    if filtered:
        return filtered
    # 无 summary 类 chunk 时回退 passage
    return list(results)


def merge_results_by_doc(results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    best_by_doc: Dict[str, Dict[str, Any]] = {}
    for item in results:
        doc_id = _derive_doc_id(item)
        prev = best_by_doc.get(doc_id)
        if prev is None or float(item.get("score", 0)) > float(prev.get("score", 0)):
            best_by_doc[doc_id] = item
    ranked = sorted(best_by_doc.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return ranked[:top_k]


def search_knowledge(
    db,
    retriever,
    query: str,
    tenant_id: str | None = None,
    collection_id: Optional[str] = None,
    top_k: int = 5,
    mode: str = "chat",
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Search all relevant collections with correct per-collection tenant_id.
    Returns (formatted_text_for_prompt, raw_results).
    mode: 'chat' (default) | 'browse' (prefer summary/key_fact, merge by doc)
    """
    if not query or not query.strip():
        return "", []
    if retriever is None or db is None:
        return "", []

    org_id = tenant_id or ORG_ID
    targets = list_collection_targets(db, org_id, collection_id=collection_id)
    if not targets:
        return "（当前账号下暂无知识库文档）", []

    all_results: List[Dict[str, Any]] = []
    per_coll_k = max(3, top_k * 2 // max(len(targets), 1)) if mode == "browse" else max(3, top_k // max(len(targets), 1))

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
                    top_k=per_coll_k * 2 if mode == "browse" else per_coll_k,
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
                    top_k=per_coll_k * 2 if mode == "browse" else per_coll_k,
                )
            except Exception as e:
                print(f"[KnowledgeAccess] SQLite 检索失败 {coll_id}@{owner_tenant}: {e}")

        all_results.extend(hits)

    if not all_results:
        return "（知识库中未找到与问题相关的内容）", []

    if mode == "browse":
        all_results = _apply_browse_filter(all_results)

    deduped: dict[str, Dict[str, Any]] = {}
    for item in all_results:
        key = item.get("id") or f"{_derive_doc_id(item)}:{_chunk_type(item)}:{item.get('text', '')[:80]}"
        if key not in deduped or float(item.get("score", 0)) > float(deduped[key].get("score", 0)):
            deduped[key] = item

    ranked = sorted(deduped.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    if mode == "browse":
        ranked = merge_results_by_doc(ranked, top_k=top_k)
    else:
        ranked = ranked[:top_k]

    ranked = [enrich_hit(r, db=db, tenant_id=org_id) for r in ranked]
    return format_citation_results(ranked), ranked
