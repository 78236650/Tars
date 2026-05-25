"""document_profiles CRUD — v4.4 知识库深度入库。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import DocProfile


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def save_profile(
    db,
    profile: DocProfile,
    *,
    tenant_id: str,
    collection_id: str,
) -> None:
    """Upsert document profile into document_profiles."""
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO document_profiles (
            doc_id, tenant_id, collection_id, doc_type, title, one_liner, summary,
            key_points_json, sections_json, key_facts_json, glossary_json,
            qa_pairs_json, tags_json, confidence, enrichment_model, enriched_at,
            parse_warnings_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            tenant_id = excluded.tenant_id,
            collection_id = excluded.collection_id,
            doc_type = excluded.doc_type,
            title = excluded.title,
            one_liner = excluded.one_liner,
            summary = excluded.summary,
            key_points_json = excluded.key_points_json,
            sections_json = excluded.sections_json,
            key_facts_json = excluded.key_facts_json,
            glossary_json = excluded.glossary_json,
            qa_pairs_json = excluded.qa_pairs_json,
            tags_json = excluded.tags_json,
            confidence = excluded.confidence,
            enrichment_model = excluded.enrichment_model,
            enriched_at = excluded.enriched_at,
            parse_warnings_json = excluded.parse_warnings_json
        """,
        (
            profile.doc_id,
            tenant_id,
            collection_id,
            profile.doc_type or "generic",
            profile.title or "",
            profile.one_liner or "",
            profile.summary or "",
            _json_dumps(profile.key_points or []),
            _json_dumps([s.to_dict() for s in (profile.sections or [])]),
            _json_dumps(profile.key_facts or []),
            _json_dumps([g.to_dict() for g in (profile.glossary or [])]),
            _json_dumps([q.to_dict() for q in (profile.qa_pairs or [])]),
            _json_dumps(profile.tags or []),
            float(profile.confidence or 0.0),
            profile.model_id,
            profile.enriched_at,
            _json_dumps(profile.parse_warnings or []),
        ),
    )
    conn.commit()


def get_profile(db, doc_id: str) -> Optional[DocProfile]:
    """Load DocProfile by doc_id; returns None if not found."""
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT doc_id, doc_type, title, one_liner, summary,
               key_points_json, sections_json, key_facts_json, glossary_json,
               qa_pairs_json, tags_json, confidence, enrichment_model, enriched_at,
               parse_warnings_json
        FROM document_profiles WHERE doc_id = ?
        """,
        (doc_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return _row_to_profile(row)


def delete_profile(db, doc_id: str) -> bool:
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM document_profiles WHERE doc_id = ?", (doc_id,))
    conn.commit()
    return cursor.rowcount > 0


def list_profiles_by_collection(db, collection_id: str) -> List[DocProfile]:
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT doc_id, doc_type, title, one_liner, summary,
               key_points_json, sections_json, key_facts_json, glossary_json,
               qa_pairs_json, tags_json, confidence, enrichment_model, enriched_at,
               parse_warnings_json
        FROM document_profiles WHERE collection_id = ?
        ORDER BY enriched_at DESC
        """,
        (collection_id,),
    )
    return [_row_to_profile(row) for row in cursor.fetchall()]


def _row_to_profile(row) -> DocProfile:
    def _loads(raw, default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    key_points = _loads(row[5], [])
    sections_raw = _loads(row[6], [])
    key_facts = _loads(row[7], [])
    glossary_raw = _loads(row[8], [])
    qa_raw = _loads(row[9], [])
    tags = _loads(row[10], [])
    parse_warnings = _loads(row[14], [])

    from .models import GlossaryItem, QAPair, SectionSummary

    return DocProfile(
        doc_id=str(row[0]),
        doc_type=str(row[1] or "generic"),
        title=str(row[2] or ""),
        one_liner=str(row[3] or ""),
        summary=str(row[4] or ""),
        key_points=[str(x) for x in key_points if x],
        sections=[SectionSummary.from_dict(s) for s in sections_raw if isinstance(s, dict)],
        key_facts=[str(x) for x in key_facts if x],
        glossary=[GlossaryItem.from_dict(g) for g in glossary_raw if isinstance(g, dict)],
        qa_pairs=[QAPair.from_dict(q) for q in qa_raw if isinstance(q, dict)],
        tags=[str(t) for t in tags if t],
        confidence=float(row[11] or 0.0),
        model_id=row[12],
        enriched_at=row[13],
        parse_warnings=list(parse_warnings or []),
    )


def profile_to_api_dict(profile: DocProfile, *, file_name: str = "", status: str = "", chunk_count: int = 0) -> Dict[str, Any]:
    """Serialize profile for GET /profile API response."""
    data = profile.to_dict()
    data["file_name"] = file_name
    data["status"] = status
    data["chunk_count"] = chunk_count
    data["profile_ready"] = True
    data["enrichment_model"] = profile.model_id
    return data
