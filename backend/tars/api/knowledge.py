"""知识库 API 路由"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..database import Database
from ..knowledge.access import search_knowledge as search_knowledge_access
from ..knowledge.collection_scope import tenant_in_sql, visible_kb_tenant_ids
from ..knowledge.config import get_enrichment_config, get_reindex_config, load_knowledge_config
from ..knowledge.schema import ensure_knowledge_schema
from ..knowledge.indexer import KnowledgeIndexer
from ..knowledge.retriever import KnowledgeRetriever
from ..reranker import CrossEncoderReranker
from ..search.query_expansion import QueryExpander
from ._auth import Principal, require_module
from .scope import org_scope

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

_require_knowledge = require_module("knowledge")


def _visible_kb_tenant_ids(principal: Principal) -> List[str]:
    return visible_kb_tenant_ids(principal.user_id)


def _resolve_collection_tenant(coll_id: str, principal: Principal) -> str:
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")
    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    cur = _db._get_conn().cursor()
    cur.execute(
        f"SELECT tenant_id FROM document_collections WHERE id = ? AND tenant_id IN ({ph})",
        (coll_id, *vals),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return row[0]


_db: Optional[Database] = None
_vector_store = None
_embedding_provider = None
_indexer: Optional[KnowledgeIndexer] = None
_retriever: Optional[KnowledgeRetriever] = None
_llm_settings_store = None  # InsightLlmSettingsStore，按租户解析 LLM provider
_knowledge_config: Optional[Dict[str, Any]] = None
_ingest_tasks: "set[asyncio.Task]" = set()
_wiki_router = None
_wiki_event_handler = None
_wiki_compile_tasks: "set[asyncio.Task]" = set()


def init_wiki_upload_routing(wiki_event_handler, wiki_router=None) -> None:
    global _wiki_event_handler, _wiki_router
    _wiki_event_handler = wiki_event_handler
    _wiki_router = wiki_router


def clear_wiki_upload_routing() -> None:
    """Reset wiki routing globals (for isolated tests)."""
    global _wiki_event_handler, _wiki_router
    _wiki_event_handler = None
    _wiki_router = None


def init_knowledge_api(
    db: Database,
    vector_store,
    embedding_provider,
    llm_settings_store=None,
    knowledge_config: Optional[Dict[str, Any]] = None,
) -> None:
    global _db, _vector_store, _embedding_provider, _indexer, _retriever, _llm_settings_store, _knowledge_config
    _db = db
    ensure_knowledge_schema(db)
    _vector_store = vector_store
    _embedding_provider = embedding_provider
    _knowledge_config = knowledge_config or load_knowledge_config()
    _indexer = KnowledgeIndexer(
        vector_store, embedding_provider, db=db, knowledge_config=_knowledge_config
    )
    _retriever = KnowledgeRetriever(
        vector_store,
        embedding_provider,
        query_expander=QueryExpander(provider=None),
        reranker=CrossEncoderReranker(),
    )
    if llm_settings_store is None:
        try:
            from ..insight.llm_settings_store import InsightLlmSettingsStore
            from ..insight.llm_resolver import init_llm_resolver

            llm_settings_store = InsightLlmSettingsStore(db)
            init_llm_resolver(db)
        except Exception as e:
            print(f"[KnowledgeAPI] LLM settings store unavailable: {e}")
            llm_settings_store = None
    _llm_settings_store = llm_settings_store


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


# ========== Pydantic 模型 ==========

class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    default_doc_type: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    collection_ids: Optional[List[str]] = None
    top_k: int = 5
    mode: str = "chat"


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "chat"


class ReindexEstimateRequest(BaseModel):
    doc_ids: Optional[List[str]] = None


class ReindexRequest(BaseModel):
    doc_ids: Optional[List[str]] = None
    confirm: bool = False


# ========== Collection CRUD ==========

@router.get("/collections")
async def list_collections(principal: Principal = Depends(_require_knowledge)):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id, name, description, default_doc_type, created_at, updated_at "
        f"FROM document_collections WHERE tenant_id IN ({ph}) ORDER BY updated_at DESC",
        vals,
    )
    rows = cursor.fetchall()
    return {
        "collections": [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "default_doc_type": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]
    }


@router.post("/collections")
async def create_collection(
    request: CreateCollectionRequest,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_id = str(uuid.uuid4())
    now = _now()
    org_id = org_scope(principal)

    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, default_doc_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (coll_id, org_id, request.name, request.description or "", request.default_doc_type, now, now),
    )
    conn.commit()

    return {
        "success": True,
        "collection": {
            "id": coll_id,
            "name": request.name,
            "description": request.description,
            "default_doc_type": request.default_doc_type,
        },
    }


@router.delete("/collections/{coll_id}")
async def delete_collection(
    coll_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_tenant = _resolve_collection_tenant(coll_id, principal)
    conn = _db._get_conn()
    cursor = conn.cursor()

    # 删除关联的文档记录
    cursor.execute("DELETE FROM document_files WHERE collection_id = ?", (coll_id,))
    # 删除集合
    cursor.execute(
        "DELETE FROM document_collections WHERE id = ? AND tenant_id = ?",
        (coll_id, coll_tenant),
    )
    conn.commit()

    # 删除向量数据库中的 collection
    if _vector_store and _vector_store.is_available:
        try:
            _vector_store.delete_collection(
                tenant_id=coll_tenant, collection_name=f"knowledge_{coll_id}"
            )
        except Exception as e:
            print(f"[KnowledgeAPI] 删除向量集合失败: {e}")

    return {"success": True, "message": "知识库已删除"}


# ========== Document Management ==========

def _parse_metric_ids(raw: Optional[str]) -> List[str]:
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    if text.startswith("["):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


_VALID_DOC_TYPES = frozenset({"policy", "proposal", "metrics", "generic"})


def _normalize_doc_type(value: Optional[str]) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized in _VALID_DOC_TYPES else None


def resolve_upload_doc_type(
    explicit: Optional[str],
    collection_default: Optional[str],
) -> tuple[Optional[str], str]:
    """解析上传 doc_type：手动 override > 集合默认 > 自动推断（parse 阶段）。

    返回 (parse_hint, response_doc_type)：
    - parse_hint 为 None 时由 structure_parser 按文件名/扩展名推断
    - response_doc_type 为 API 立即返回的占位值（auto 时为 generic）
    """
    manual = _normalize_doc_type(explicit)
    if manual:
        return manual, manual
    inherited = _normalize_doc_type(collection_default)
    if inherited:
        return inherited, inherited
    return None, "generic"


def _file_format_from_name(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    return ext or "bin"


def _decode_upload_text(content: bytes, file_format: str) -> str:
    if file_format in ("md", "txt"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")
    return ""


def _schedule_wiki_compile(text: str, file_name: str) -> None:
    if _wiki_event_handler is None:
        return
    task = asyncio.create_task(
        _wiki_event_handler.on_small_file_uploaded(text, file_name)
    )
    _wiki_compile_tasks.add(task)
    task.add_done_callback(_wiki_compile_tasks.discard)


@router.post("/collections/{coll_id}/documents")
async def upload_document(
    coll_id: str,
    file: UploadFile = File(...),
    metric_ids: Optional[str] = Form(default=None),
    doc_type: Optional[str] = Form(default=None),
    target: str = Query(default="auto", pattern="^(auto|wiki|rag)$"),
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_tenant = _resolve_collection_tenant(coll_id, principal)

    # 验证集合存在并取默认 doc_type
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, default_doc_type FROM document_collections WHERE id = ? AND tenant_id = ?",
        (coll_id, coll_tenant),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="知识库不存在")
    collection_default_doc_type = row[1] if len(row) > 1 else None
    parse_doc_type, response_doc_type = resolve_upload_doc_type(doc_type, collection_default_doc_type)

    # 保存文件
    doc_id = str(uuid.uuid4())
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "knowledge")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, f"{doc_id}_{file.filename}")

    try:
        content = await file.read()
        file_format = _file_format_from_name(file.filename or "")
        text_preview = _decode_upload_text(content, file_format)
        text_size = len(text_preview) if text_preview else len(content)

        route_decision = "rag"
        route_reason = "default_rag"
        if _wiki_router is not None:
            from tars.wiki.router import WikiRagRouter

            router = _wiki_router or WikiRagRouter(llm_provider=None)
            user_override = target if target != "auto" else None
            route_decision = router.route(
                page_count=None,
                text_size=text_size,
                file_name=file.filename or "",
                file_format=file_format,
                user_override=user_override,
            )
            if route_decision == "llm_decide":
                route_decision = await router.route_with_llm_fallback(
                    page_count=None,
                    text_size=text_size,
                    file_name=file.filename or "",
                    file_format=file_format,
                    user_override=user_override,
                    text_preview=text_preview,
                )
            route_reason = "rule_engine" if target == "auto" else f"user_override_{target}"

        if route_decision == "wiki" and _wiki_event_handler is not None:
            if not text_preview:
                route_decision = "rag"
                route_reason = "wiki_unsupported_format_fallback_rag"
            else:
                _schedule_wiki_compile(text_preview, file.filename or "upload")
                return {
                    "success": True,
                    "routed_to": "wiki",
                    "route_reason": route_reason,
                    "document": {
                        "file_name": file.filename,
                        "status": "compiling",
                    },
                }

        with open(file_path, "wb") as f:
            f.write(content)

        now = _now()
        cursor.execute(
            "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, "
            "doc_type, profile_ready, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (doc_id, coll_id, file.filename, file_path, file.content_type or "", "pending",
             response_doc_type, now),
        )
        conn.commit()

        parsed_metric_ids = _parse_metric_ids(metric_ids)
        if parsed_metric_ids:
            from ..knowledge.sqlite_store import set_document_metadata

            set_document_metadata(
                _db,
                doc_id,
                {"metric_ids": parsed_metric_ids, "collection_id": coll_id},
            )

        # 异步入库，立即返回 pending
        _schedule_ingest(
            doc_id=doc_id,
            file_path=file_path,
            collection_id=coll_id,
            tenant_id=coll_tenant,
            doc_type=parse_doc_type,
        )

        return {
            "success": True,
            "routed_to": "rag",
            "route_reason": route_reason,
            "document": {
                "id": doc_id,
                "file_name": file.filename,
                "status": "pending",
                "profile_ready": False,
                "doc_type": response_doc_type,
                "doc_type_source": (
                    "override"
                    if _normalize_doc_type(doc_type)
                    else "collection_default"
                    if _normalize_doc_type(collection_default_doc_type)
                    else "auto"
                ),
                "metric_ids": parsed_metric_ids,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


def _schedule_ingest(
    *,
    doc_id: str,
    file_path: str,
    collection_id: str,
    tenant_id: str,
    doc_type: Optional[str],
) -> None:
    """异步调度入库管线（参考 api/meeting.py:_schedule_transcription）。"""
    task = asyncio.create_task(
        _run_ingest(doc_id=doc_id, file_path=file_path, collection_id=collection_id,
                    tenant_id=tenant_id, doc_type=doc_type)
    )
    _ingest_tasks.add(task)
    task.add_done_callback(_ingest_tasks.discard)


async def _run_ingest(
    *,
    doc_id: str,
    file_path: str,
    collection_id: str,
    tenant_id: str,
    doc_type: Optional[str],
) -> None:
    """状态机：pending → parsing → enriching → indexing → ready / 失败分支。"""
    if _db is None or _indexer is None:
        return

    file_name = os.path.basename(file_path).split("_", 1)[-1]
    file_type = os.path.splitext(file_name)[1].lower()

    # parsing
    _db.update_document_file(doc_id, status="parsing")
    try:
        from ..knowledge.structure_parser import parse_to_document

        parsed = await asyncio.to_thread(parse_to_document, file_path, doc_type)
    except Exception as e:
        _db.update_document_file(doc_id, status="failed", status_message=f"parse_error: {e}")
        print(f"[KnowledgeIngest] parse failed {doc_id}: {e}")
        return

    effective_doc_type = doc_type or parsed.doc_type_hint or "generic"
    _db.update_document_file(doc_id, doc_type=effective_doc_type)

    if not parsed.plain_text and not parsed.sections and not parsed.metrics_tables:
        _db.update_document_file(doc_id, status="failed", status_message="empty_content")
        return

    # enriching
    profile = None
    enrichment_failed = False
    _db.update_document_file(doc_id, status="enriching")
    try:
        from ..knowledge.enricher import enrich_document

        profile = await asyncio.to_thread(
            enrich_document,
            parsed,
            tenant_id=tenant_id,
            doc_id=doc_id,
            doc_type=effective_doc_type,
            llm_settings_store=_llm_settings_store,
            file_name=file_name,
            config=get_enrichment_config(),
        )
    except Exception as e:
        enrichment_failed = True
        print(f"[KnowledgeIngest] enrich failed {doc_id}: {e}")

    # indexing
    _db.update_document_file(doc_id, status="indexing")
    try:
        result = await asyncio.to_thread(
            _indexer.index_parsed,
            parsed,
            profile,
            doc_id,
            collection_id,
            file_name,
            file_type,
            tenant_id,
        )
    except Exception as e:
        _db.update_document_file(doc_id, status="failed", status_message=f"index_error: {e}")
        return

    if result.get("status") != "indexed":
        _db.update_document_file(
            doc_id,
            status="failed",
            status_message=f"index_failed: {result.get('error') or result.get('status')}",
        )
        return

    # 持久化 profile
    if profile is not None:
        try:
            from ..knowledge.profile_store import save_profile

            save_profile(_db, profile, tenant_id=tenant_id, collection_id=collection_id)
        except Exception as e:
            print(f"[KnowledgeIngest] save_profile failed {doc_id}: {e}")
            enrichment_failed = True

    final_status = "enrichment_failed" if (enrichment_failed or profile is None) else "ready"
    status_message = None
    if final_status == "enrichment_failed":
        if enrichment_failed:
            status_message = "enrichment_error"
        elif profile is None:
            status_message = "enrichment_no_profile: 请在「模型配置」选择与 Chat 相同的模型后重新理解"
    _db.update_document_file(
        doc_id,
        status=final_status,
        chunk_count=int(result.get("chunk_count") or 0),
        profile_ready=bool(profile is not None and not enrichment_failed),
        one_liner=(profile.one_liner if profile else None),
        doc_type=(profile.doc_type if profile else effective_doc_type),
        status_message=status_message,
    )


@router.get("/collections/{coll_id}/documents/{doc_id}/profile")
async def get_document_profile(
    coll_id: str,
    doc_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")

    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    conn = _db._get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT df.id, df.file_name, df.status, df.chunk_count FROM document_files df "
        f"JOIN document_collections dc ON dc.id = df.collection_id "
        f"WHERE df.id = ? AND df.collection_id = ? AND dc.tenant_id IN ({ph})",
        (doc_id, coll_id, *vals),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")

    from ..knowledge.profile_store import get_profile, profile_to_api_dict

    profile = get_profile(_db, doc_id)
    if profile is None:
        doc = _db.get_document_file(doc_id)
        return {
            "doc_id": doc_id,
            "file_name": row[1],
            "status": row[2],
            "profile_ready": False,
            "chunk_count": row[3] or 0,
        }

    return profile_to_api_dict(
        profile,
        file_name=row[1] or "",
        status=row[2] or "",
        chunk_count=int(row[3] or 0),
    )


@router.get("/collections/{coll_id}/documents/{doc_id}/passages")
async def get_document_passages(
    coll_id: str,
    doc_id: str,
    section_id: Optional[str] = None,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")

    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    conn = _db._get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT df.id FROM document_files df JOIN document_collections dc ON dc.id = df.collection_id "
        f"WHERE df.id = ? AND df.collection_id = ? AND dc.tenant_id IN ({ph})",
        (doc_id, coll_id, *vals),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="文档不存在")

    from ..knowledge.sqlite_store import ensure_knowledge_chunks_table, get_passage_chunks

    ensure_knowledge_chunks_table(_db)
    passages = get_passage_chunks(_db, doc_id, section_id=section_id)
    return {"doc_id": doc_id, "section_id": section_id, "passages": passages}


@router.post("/collections/{coll_id}/documents/{doc_id}/re-enrich")
async def re_enrich_document(
    coll_id: str,
    doc_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_tenant = _resolve_collection_tenant(coll_id, principal)
    doc = _db.get_document_file(doc_id)
    if not doc or doc.get("collection_id") != coll_id:
        raise HTTPException(status_code=404, detail="文档不存在")

    file_path = doc.get("file_path")
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="源文件不存在，无法重新理解")

    _db.update_document_file(doc_id, status="pending", profile_ready=False, status_message=None)
    _schedule_ingest(
        doc_id=doc_id,
        file_path=file_path,
        collection_id=coll_id,
        tenant_id=coll_tenant,
        doc_type=doc.get("doc_type") or "generic",
    )
    return {"success": True, "doc_id": doc_id, "status": "pending"}


@router.get("/collections/{coll_id}/documents/{doc_id}/status")
async def get_document_status(
    coll_id: str,
    doc_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    """轻量轮询：仅返回 status / profile_ready / one_liner。"""
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")
    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    conn = _db._get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT df.id FROM document_files df JOIN document_collections dc ON dc.id = df.collection_id "
        f"WHERE df.id = ? AND df.collection_id = ? AND dc.tenant_id IN ({ph})",
        (doc_id, coll_id, *vals),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="文档不存在")
    doc = _db.get_document_file(doc_id)
    return {
        "doc_id": doc_id,
        "status": doc.get("status"),
        "profile_ready": doc.get("profile_ready"),
        "one_liner": doc.get("one_liner"),
        "doc_type": doc.get("doc_type"),
        "chunk_count": doc.get("chunk_count"),
        "status_message": doc.get("status_message"),
    }


@router.post("/collections/{coll_id}/batch")
async def batch_upload_documents(
    coll_id: str,
    files: List[UploadFile] = File(...),
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_tenant = _resolve_collection_tenant(coll_id, principal)

    total = len(files)
    indexed = 0
    failed: list[dict[str, str]] = []
    documents: list[dict[str, Any]] = []

    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "knowledge")
    os.makedirs(uploads_dir, exist_ok=True)
    conn = _db._get_conn()
    cursor = conn.cursor()

    for file in files:
        doc_id = str(uuid.uuid4())
        file_path = os.path.join(uploads_dir, f"{doc_id}_{file.filename}")
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            now = _now()
            cursor.execute(
                "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, coll_id, file.filename, file_path, file.content_type or "", 0, "pending", now),
            )
            conn.commit()

            result = _indexer.index_file(
                file_path=file_path,
                doc_id=doc_id,
                collection_id=coll_id,
                tenant_id=coll_tenant,
            )
            cursor.execute(
                "UPDATE document_files SET chunk_count = ?, status = ? WHERE id = ?",
                (result["chunk_count"], result["status"], doc_id),
            )
            conn.commit()

            if result["status"] == "indexed":
                indexed += 1
                documents.append(
                    {
                        "id": doc_id,
                        "file_name": file.filename,
                        "chunk_count": result["chunk_count"],
                        "status": result["status"],
                    }
                )
            else:
                failed.append({"file": file.filename, "error": result.get("error", result["status"])})
        except Exception as e:
            failed.append({"file": file.filename, "error": str(e)})

    return {
        "total": total,
        "indexed": indexed,
        "failed": failed,
        "documents": documents,
    }


@router.get("/collections/{coll_id}/documents")
async def list_documents(
    coll_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_ids = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(tenant_ids)
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT df.id, df.file_name, df.file_type, df.chunk_count, df.status, df.doc_type, df.profile_ready, df.one_liner, df.created_at "
        f"FROM document_files df "
        f"JOIN document_collections dc ON dc.id = df.collection_id "
        f"WHERE df.collection_id = ? AND dc.tenant_id IN ({ph}) ORDER BY df.created_at DESC",
        (coll_id, *vals),
    )
    rows = cursor.fetchall()
    return {
        "documents": [
            {
                "id": r[0],
                "file_name": r[1],
                "file_type": r[2],
                "chunk_count": r[3],
                "status": r[4],
                "doc_type": r[5] or "generic",
                "profile_ready": bool(r[6]),
                "one_liner": r[7],
                "created_at": r[8],
            }
            for r in rows
        ]
    }


@router.delete("/collections/{coll_id}/documents/{doc_id}")
async def delete_document(
    coll_id: str,
    doc_id: str,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    if _indexer is None:
        raise HTTPException(status_code=500, detail="知识库索引器未初始化")

    coll_tenant = _resolve_collection_tenant(coll_id, principal)
    deleted = _indexer.delete_document(
        doc_id=doc_id,
        collection_id=coll_id,
        tenant_id=coll_tenant,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在或删除失败")

    return {"success": True, "message": "文档已删除"}


# ========== Search ==========

@router.post("/search")
async def search_knowledge_endpoint(
    request: SearchRequest,
    principal: Principal = Depends(_require_knowledge),
):
    if _retriever is None:
        raise HTTPException(status_code=500, detail="知识库检索器未初始化")

    visible = _visible_kb_tenant_ids(principal)
    mode = request.mode or "chat"
    if request.collection_ids:
        results = []
        for coll_id in request.collection_ids:
            _, hits = search_knowledge_access(
                _db,
                _retriever,
                request.query,
                tenant_ids=visible,
                collection_id=coll_id,
                top_k=request.top_k,
                mode=mode,
            )
            results.extend(hits)
        if mode == "browse":
            from ..knowledge.access import merge_results_by_doc
            results = merge_results_by_doc(results, request.top_k)
    else:
        _, results = search_knowledge_access(
            _db,
            _retriever,
            request.query,
            tenant_ids=visible,
            top_k=request.top_k,
            mode=mode,
        )

    return {
        "query": request.query,
        "mode": mode,
        "results": results,
        "total": len(results),
    }


@router.post("/collections/{coll_id}/query")
async def query_collection(
    coll_id: str,
    request: QueryRequest,
    principal: Principal = Depends(_require_knowledge),
):
    if _retriever is None:
        raise HTTPException(status_code=500, detail="知识库检索器未初始化")

    visible = _visible_kb_tenant_ids(principal)
    mode = request.mode or "chat"
    _, results = search_knowledge_access(
        _db,
        _retriever,
        request.query,
        tenant_ids=visible,
        collection_id=coll_id,
        top_k=request.top_k,
        mode=mode,
    )

    return {
        "query": request.query,
        "collection_id": coll_id,
        "mode": mode,
        "results": results,
        "total": len(results),
    }


def _collection_doc_ids(
    coll_id: str,
    tenant_ids: List[str],
    doc_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    conn = _db._get_conn()
    cur = conn.cursor()
    ph, vals = tenant_in_sql(tenant_ids)
    if doc_ids:
        doc_ph = ",".join("?" * len(doc_ids))
        cur.execute(
            f"SELECT df.id, df.file_path, df.doc_type FROM document_files df "
            f"JOIN document_collections dc ON dc.id = df.collection_id "
            f"WHERE df.collection_id = ? AND dc.tenant_id IN ({ph}) AND df.id IN ({doc_ph})",
            [coll_id, *vals, *doc_ids],
        )
    else:
        cur.execute(
            f"SELECT df.id, df.file_path, df.doc_type FROM document_files df "
            f"JOIN document_collections dc ON dc.id = df.collection_id "
            f"WHERE df.collection_id = ? AND dc.tenant_id IN ({ph})",
            (coll_id, *vals),
        )
    return [{"id": r[0], "file_path": r[1], "doc_type": r[2] or "generic"} for r in cur.fetchall()]


@router.post("/collections/{coll_id}/reindex/estimate")
async def reindex_estimate(
    coll_id: str,
    request: ReindexEstimateRequest,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")
    visible = _visible_kb_tenant_ids(principal)
    docs = _collection_doc_ids(coll_id, visible, request.doc_ids)
    if not docs:
        raise HTTPException(status_code=404, detail="未找到待重建文档")
    coll_tenant = _resolve_collection_tenant(coll_id, principal)
    cfg = get_reindex_config()
    per_doc = int(cfg.get("estimate_tokens_per_doc", 8000))
    doc_count = len(docs)
    est_tokens = doc_count * per_doc
    return {
        "doc_count": doc_count,
        "est_tokens": est_tokens,
        "require_confirm": doc_count >= int(cfg.get("require_confirm_above_doc_count", 5)),
        "doc_ids": [d["id"] for d in docs],
    }


@router.post("/collections/{coll_id}/reindex")
async def reindex_collection(
    coll_id: str,
    request: ReindexRequest,
    principal: Principal = Depends(_require_knowledge),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    visible = _visible_kb_tenant_ids(principal)
    docs = _collection_doc_ids(coll_id, visible, request.doc_ids)
    if not docs:
        raise HTTPException(status_code=404, detail="未找到待重建文档")
    coll_tenant = _resolve_collection_tenant(coll_id, principal)

    cfg = get_reindex_config()
    threshold = int(cfg.get("require_confirm_above_doc_count", 5))
    if len(docs) >= threshold and not request.confirm:
        per_doc = int(cfg.get("estimate_tokens_per_doc", 8000))
        raise HTTPException(
            status_code=412,
            detail={
                "message": "文档数量较多，请确认后重建",
                "doc_count": len(docs),
                "est_tokens": len(docs) * per_doc,
                "require_confirm": True,
            },
        )

    scheduled = 0
    for doc in docs:
        file_path = doc.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            continue
        doc_id = doc["id"]
        _db.update_document_file(doc_id, status="pending", profile_ready=False, status_message=None)
        _schedule_ingest(
            doc_id=doc_id,
            file_path=file_path,
            collection_id=coll_id,
            tenant_id=coll_tenant,
            doc_type=doc.get("doc_type") or "generic",
        )
        scheduled += 1

    return {"success": True, "scheduled": scheduled, "status": "pending"}


def _fetch_ref_snippet(cursor, doc_id: str, tenant_ids: List[str], limit: int = 400) -> str:
    for tid in tenant_ids:
        cursor.execute(
            """
            SELECT content FROM knowledge_chunks
            WHERE doc_id = ? AND tenant_id = ?
            ORDER BY chunk_index ASC
            LIMIT 1
            """,
            (doc_id, tid),
        )
        row = cursor.fetchone()
        if row and row[0]:
            text = str(row[0]).strip()
            if len(text) > limit:
                return text[:limit] + "..."
            return text
    return ""


@router.get("/ref/{doc_id}")
async def resolve_document_ref(
    doc_id: str,
    principal: Principal = Depends(require_module("knowledge")),
):
    """Resolve a [ref:doc_id] citation to title and preview snippet."""
    if _db is None:
        raise HTTPException(status_code=500, detail="数据库未初始化")

    visible = _visible_kb_tenant_ids(principal)
    ph, vals = tenant_in_sql(visible)
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT df.id, df.file_name, df.collection_id
           FROM document_files df
           JOIN document_collections dc ON dc.id = df.collection_id
           WHERE df.id = ? AND dc.tenant_id IN ({ph})""",
        (doc_id, *vals),
    )
    row = cursor.fetchone()
    if row:
        from ..knowledge.profile_store import get_profile

        profile = get_profile(_db, doc_id)
        chunk_excerpt = _fetch_ref_snippet(cursor, doc_id, visible)
        one_liner = None
        summary_excerpt = None
        doc_type = None
        profile_ready = False
        if profile:
            one_liner = profile.one_liner
            summary_excerpt = (profile.summary or "")[:200]
            doc_type = profile.doc_type
            profile_ready = True
        else:
            doc_row = _db.get_document_file(doc_id)
            if doc_row:
                one_liner = doc_row.get("one_liner")
                doc_type = doc_row.get("doc_type")
                profile_ready = bool(doc_row.get("profile_ready"))
        return {
            "doc_id": row[0],
            "title": row[1] or doc_id,
            "collection_id": row[2],
            "snippet": chunk_excerpt,
            "chunk_excerpt": chunk_excerpt,
            "one_liner": one_liner,
            "summary_excerpt": summary_excerpt,
            "doc_type": doc_type,
            "profile_ready": profile_ready,
            "source_type": "document",
        }

    chunk_ph, chunk_vals = tenant_in_sql(visible)
    cursor.execute(
        f"""
        SELECT doc_id, file_name, collection_id, content
        FROM knowledge_chunks
        WHERE doc_id = ? AND tenant_id IN ({chunk_ph})
        ORDER BY chunk_index ASC
        LIMIT 1
        """,
        (doc_id, *chunk_vals),
    )
    chunk = cursor.fetchone()
    if chunk:
        snippet = str(chunk[3] or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        return {
            "doc_id": chunk[0],
            "title": chunk[1] or doc_id,
            "collection_id": chunk[2],
            "snippet": snippet,
            "source_type": "document",
        }

    raise HTTPException(status_code=404, detail=f"未找到文档引用: {doc_id}")
