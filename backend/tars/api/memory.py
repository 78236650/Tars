"""Memory management REST API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..database import Database
from ..memory.compressor import MemoryCompressor
from ..memory.core_memory import BLOCK_NAMES
from ..memory.manager import MemoryManager

router = APIRouter(prefix="/api/memory", tags=["memory"])

_db: Optional[Database] = None
_memory_manager: Optional[MemoryManager] = None
_compressor: Optional[MemoryCompressor] = None


def init_memory_api(db: Database, memory_manager: MemoryManager):
    global _db, _memory_manager, _compressor
    _db = db
    _memory_manager = memory_manager
    _compressor = memory_manager.compressor


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


def _require_manager() -> MemoryManager:
    if _memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")
    return _memory_manager


def _require_compressor() -> MemoryCompressor:
    if _compressor is None:
        raise HTTPException(status_code=500, detail="Memory compressor not initialized")
    return _compressor


def _memory_to_dict(memory) -> Dict[str, Any]:
    entity_refs = []
    for ref in (memory.entity_refs or []):
        entity_refs.append(ref.get("name", str(ref)) if isinstance(ref, dict) else ref)
    return {
        "id": memory.id,
        "content": memory.content,
        "summary": memory.content[:100],
        "category": memory.category,
        "importance": memory.importance,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
        "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else None,
        "source": memory.source,
        "pinned": memory.pinned,
        "compressed_from": memory.compressed_from or [],
        "memory_type": memory.memory_type,
        "event_time": memory.event_time.isoformat() if memory.event_time else None,
        "entity_refs": entity_refs,
    }


class UpdateCoreBlockRequest(BaseModel):
    content: str = Field(min_length=1)


class UpdateMemoryRequest(BaseModel):
    content: str = Field(min_length=1)


class PinRequest(BaseModel):
    pinned: bool = True


class MergeRequest(BaseModel):
    memory_ids: List[str] = Field(min_length=2)
    preview_only: bool = True


@router.get("/stats")
def get_memory_stats(x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    compressor = _require_compressor()
    tenant_id = x_tenant_id or "default"
    stats = db.get_memory_stats(tenant_id=tenant_id)
    status = compressor.status()
    stats["last_compressed_at"] = status.get("last_finished_at")
    return stats


@router.get("/core")
def get_core_memory():
    manager = _require_manager()
    return {"blocks": manager.core.get_all()}


@router.put("/core/{block}")
def update_core_memory(block: str, payload: UpdateCoreBlockRequest):
    manager = _require_manager()
    if block not in BLOCK_NAMES:
        raise HTTPException(status_code=400, detail="invalid core memory block")
    manager.core.set(block, payload.content)
    return {"success": True, "block": block, "content": payload.content}


@router.get("/recent")
def get_recent_memories(
    page: int = 1,
    q: str = "",
    cat: str = "",
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    items, total = db.list_recent_memories(page=page, query=q, category=cat, tenant_id=tenant_id)
    return {
        "items": [_memory_to_dict(item) for item in items],
        "page": page,
        "page_size": 20,
        "total": total,
    }


@router.get("/longterm")
def get_longterm_memories(
    page: int = 1,
    group_by: str = "entity",
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    memories, total = db.list_longterm_memories(tenant_id=tenant_id, page=page, page_size=20)

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for memory in memories:
        if group_by == "entity" and memory.entity_refs:
            ref = memory.entity_refs[0]
            group_name = ref.get("name", str(ref)) if isinstance(ref, dict) else str(ref)
        else:
            group_name = "通用"
        groups.setdefault(group_name, []).append(_memory_to_dict(memory))

    return {
        "page": page,
        "page_size": 20,
        "total": total,
        "groups": [{"group_name": name, "items": items} for name, items in groups.items()],
    }


@router.get("/all")
def get_all_memories(
    page: int = 1,
    q: str = "",
    cat: str = "",
    memory_type: str = "",
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    items, total = db.list_all_memories(
        page=page,
        query=q,
        category=cat,
        memory_type=memory_type,
        tenant_id=tenant_id,
    )
    return {
        "items": [_memory_to_dict(item) for item in items],
        "page": page,
        "page_size": 20,
        "total": total,
    }


@router.get("/compress/status")
def get_compress_status():
    compressor = _require_compressor()
    return compressor.status()


@router.post("/compress")
async def run_manual_compress():
    compressor = _require_compressor()
    return await compressor.compress_all()


@router.post("/merge")
async def merge_memories(payload: MergeRequest):
    compressor = _require_compressor()
    try:
        return await compressor.merge_memories(payload.memory_ids, preview_only=payload.preview_only)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{memory_id}")
def get_memory_detail(memory_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    memory = db.get_memory(memory_id, tenant_id=x_tenant_id or "default")
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _memory_to_dict(memory)


@router.put("/{memory_id}")
def update_memory(memory_id: str, payload: UpdateMemoryRequest, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    ok = db.update_memory(memory_id, payload.content, tenant_id=x_tenant_id or "default")
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    memory = db.get_memory(memory_id, tenant_id=x_tenant_id or "default")
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    ok = db.delete_memory(memory_id, tenant_id=x_tenant_id or "default")
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"success": True}


@router.post("/{memory_id}/pin")
def pin_memory(memory_id: str, payload: PinRequest, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    ok = db.set_memory_pin(memory_id, payload.pinned, tenant_id=x_tenant_id or "default")
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"success": True, "pinned": payload.pinned}


@router.post("/{memory_id}/promote")
def promote_memory(memory_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    memory = db.promote_memory(memory_id, tenant_id=x_tenant_id or "default")
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _memory_to_dict(memory)
