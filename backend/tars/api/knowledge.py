"""知识库 API 路由"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..database import Database
from ..knowledge.indexer import KnowledgeIndexer
from ..knowledge.retriever import KnowledgeRetriever
from ..reranker import CrossEncoderReranker
from ..search.query_expansion import QueryExpander

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

_db: Optional[Database] = None
_vector_store = None
_embedding_provider = None
_indexer: Optional[KnowledgeIndexer] = None
_retriever: Optional[KnowledgeRetriever] = None


def init_knowledge_api(db: Database, vector_store, embedding_provider) -> None:
    global _db, _vector_store, _embedding_provider, _indexer, _retriever
    _db = db
    _vector_store = vector_store
    _embedding_provider = embedding_provider
    _indexer = KnowledgeIndexer(vector_store, embedding_provider, db=db)
    _retriever = KnowledgeRetriever(
        vector_store,
        embedding_provider,
        query_expander=QueryExpander(provider=None),
        reranker=CrossEncoderReranker(),
    )


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


# ========== Pydantic 模型 ==========

class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class SearchRequest(BaseModel):
    query: str
    collection_ids: Optional[List[str]] = None
    top_k: int = 5


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


# ========== Collection CRUD ==========

@router.get("/collections")
async def list_collections(x_tenant_id: Optional[str] = Header(default="default")):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, description, created_at, updated_at FROM document_collections WHERE tenant_id = ? ORDER BY updated_at DESC",
        (x_tenant_id or "default",),
    )
    rows = cursor.fetchall()
    return {
        "collections": [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "created_at": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]
    }


@router.post("/collections")
async def create_collection(
    request: CreateCollectionRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    coll_id = str(uuid.uuid4())
    now = _now()
    tenant_id = x_tenant_id or "default"

    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (coll_id, tenant_id, request.name, request.description or "", now, now),
    )
    conn.commit()

    return {"success": True, "collection": {"id": coll_id, "name": request.name, "description": request.description}}


@router.delete("/collections/{coll_id}")
async def delete_collection(
    coll_id: str,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_id = x_tenant_id or "default"
    conn = _db._get_conn()
    cursor = conn.cursor()

    # 删除关联的文档记录
    cursor.execute("DELETE FROM document_files WHERE collection_id = ?", (coll_id,))
    # 删除集合
    cursor.execute("DELETE FROM document_collections WHERE id = ? AND tenant_id = ?", (coll_id, tenant_id))
    conn.commit()

    # 删除向量数据库中的 collection
    if _vector_store and _vector_store.is_available:
        try:
            _vector_store.delete_collection(tenant_id=tenant_id, collection_name=f"knowledge_{coll_id}")
        except Exception as e:
            print(f"[KnowledgeAPI] 删除向量集合失败: {e}")

    return {"success": True, "message": "知识库已删除"}


# ========== Document Management ==========

@router.post("/collections/{coll_id}/documents")
async def upload_document(
    coll_id: str,
    file: UploadFile = File(...),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_id = x_tenant_id or "default"

    # 验证集合存在
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM document_collections WHERE id = ? AND tenant_id = ?",
        (coll_id, tenant_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 保存文件
    doc_id = str(uuid.uuid4())
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "knowledge")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, f"{doc_id}_{file.filename}")

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # 插入文档记录
        now = _now()
        cursor.execute(
            "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, coll_id, file.filename, file_path, file.content_type or "", "pending", now),
        )
        conn.commit()

        result = _indexer.index_file(
            file_path=file_path,
            doc_id=doc_id,
            collection_id=coll_id,
            tenant_id=tenant_id,
        )

        # 更新状态
        cursor.execute(
            "UPDATE document_files SET chunk_count = ?, status = ? WHERE id = ?",
            (result["chunk_count"], result["status"], doc_id),
        )
        conn.commit()

        return {
            "success": True,
            "document": {
                "id": doc_id,
                "file_name": file.filename,
                "chunk_count": result["chunk_count"],
                "status": result["status"],
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.post("/collections/{coll_id}/batch")
async def batch_upload_documents(
    coll_id: str,
    files: List[UploadFile] = File(...),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_id = x_tenant_id or "default"
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM document_collections WHERE id = ? AND tenant_id = ?",
        (coll_id, tenant_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="知识库不存在")

    total = len(files)
    indexed = 0
    failed: list[dict[str, str]] = []
    documents: list[dict[str, Any]] = []

    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "knowledge")
    os.makedirs(uploads_dir, exist_ok=True)

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
                tenant_id=tenant_id,
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
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, file_name, file_type, chunk_count, status, created_at FROM document_files WHERE collection_id = ? ORDER BY created_at DESC",
        (coll_id,),
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
                "created_at": r[5],
            }
            for r in rows
        ]
    }


@router.delete("/collections/{coll_id}/documents/{doc_id}")
async def delete_document(
    coll_id: str,
    doc_id: str,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    if _indexer is None:
        raise HTTPException(status_code=500, detail="知识库索引器未初始化")

    deleted = _indexer.delete_document(
        doc_id=doc_id,
        collection_id=coll_id,
        tenant_id=x_tenant_id or "default",
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在或删除失败")

    return {"success": True, "message": "文档已删除"}


# ========== Search ==========

@router.post("/search")
async def search_knowledge(
    request: SearchRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _retriever is None:
        raise HTTPException(status_code=500, detail="知识库检索器未初始化")

    collection_ids = request.collection_ids or []
    if not collection_ids:
        # 如果没有指定，搜索所有集合
        conn = _db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM document_collections WHERE tenant_id = ?",
            (x_tenant_id or "default",),
        )
        collection_ids = [r[0] for r in cursor.fetchall()]

    results = _retriever.retrieve(
        query=request.query,
        collection_ids=collection_ids,
        top_k=request.top_k,
        tenant_id=x_tenant_id or "default",
    )

    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


@router.post("/collections/{coll_id}/query")
async def query_collection(
    coll_id: str,
    request: QueryRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _retriever is None:
        raise HTTPException(status_code=500, detail="知识库检索器未初始化")

    results = _retriever.retrieve(
        query=request.query,
        collection_ids=[coll_id],
        top_k=request.top_k,
        tenant_id=x_tenant_id or "default",
    )

    return {
        "query": request.query,
        "collection_id": coll_id,
        "results": results,
        "total": len(results),
    }
