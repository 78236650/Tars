"""Memory management REST API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import Database
from ..memory.compressor import MemoryCompressor
from ..memory.core_memory import BLOCK_NAMES
from ..memory.manager import MemoryManager
from ..security.audit import safe_audit, client_ip_from_request

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


def _tenant_manager(tenant_id: Optional[str]) -> MemoryManager:
    return _require_manager().for_tenant((tenant_id or "default").strip() or "default")


def _require_compressor() -> MemoryCompressor:
    if _compressor is None:
        raise HTTPException(status_code=500, detail="Memory compressor not initialized")
    return _compressor


def _tenant_compressor(tenant_id: Optional[str]) -> MemoryCompressor:
    base = _require_compressor()
    scoped_tenant = (tenant_id or "default").strip() or "default"
    return MemoryCompressor(base.db, provider=base.provider, tenant_id=scoped_tenant)


def _audit_memory_write(
    action: str,
    memory_id: str,
    tenant_id: str,
    http_request: Optional[Request] = None,
):
    safe_audit(
        lambda lg: lg.log_memory_access(
            memory_id=memory_id,
            action=action,
            tenant_id=tenant_id,
            user_id=tenant_id,
            client_ip=client_ip_from_request(http_request),
        )
    )


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
        "tenant_id": getattr(memory, "tenant_id", "default"),
        "scope": getattr(memory, "scope", "private"),
    }


class UpdateCoreBlockRequest(BaseModel):
    content: str = ""


class UpdateMemoryRequest(BaseModel):
    content: str = Field(min_length=1)


class PinRequest(BaseModel):
    pinned: bool = True


class MergeRequest(BaseModel):
    memory_ids: List[str] = Field(min_length=2)
    preview_only: bool = True


class ExtractTurnRequest(BaseModel):
    user_content: str = Field(default="", max_length=8000)
    assistant_content: str = Field(min_length=1, max_length=50000)


class MemoryDraftItem(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="fact")
    importance: float = Field(default=0.75, ge=0.0, le=1.0)


class SaveTurnMemoriesRequest(BaseModel):
    items: List[MemoryDraftItem] = Field(min_length=1, max_length=10)


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
def get_core_memory(x_tenant_id: Optional[str] = Header(default="default")):
    manager = _tenant_manager(x_tenant_id)
    return {"blocks": manager.core.get_all(), "tenant_id": manager.tenant_id}


@router.put("/core/{block}")
def update_core_memory(
    block: str,
    payload: UpdateCoreBlockRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    manager = _tenant_manager(x_tenant_id)
    if block not in BLOCK_NAMES:
        raise HTTPException(status_code=400, detail="invalid core memory block")
    manager.core.set(block, payload.content)
    safe_audit(
        lambda lg: lg.log_config_change(
            resource_id=f"core_memory:{block}",
            detail="memory_write",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {
        "success": True,
        "block": block,
        "content": payload.content,
        "tenant_id": manager.tenant_id,
    }


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
async def run_manual_compress(x_tenant_id: Optional[str] = Header(default="default")):
    compressor = _tenant_compressor(x_tenant_id)
    report = await compressor.compress_all()
    _require_compressor()._status = compressor._status
    return report


@router.post("/merge")
async def merge_memories(
    payload: MergeRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    compressor = _tenant_compressor(x_tenant_id)
    try:
        return await compressor.merge_memories(payload.memory_ids, preview_only=payload.preview_only)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/extract-from-turn")
async def extract_memories_from_turn(
    payload: ExtractTurnRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    manager = _tenant_manager(x_tenant_id)
    items = await manager.extract_turn_memories(payload.user_content, payload.assistant_content)
    return {"items": items}


@router.post("/save-from-turn")
async def save_memories_from_turn(
    payload: SaveTurnMemoriesRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    manager = _tenant_manager(x_tenant_id)
    tenant_id = x_tenant_id or "default"
    allowed = {"fact", "preference", "decision", "domain_knowledge"}
    for item in payload.items:
        if item.category not in allowed:
            raise HTTPException(status_code=400, detail=f"invalid category: {item.category}")

    result = await manager.save_turn_memories([item.model_dump() for item in payload.items])
    for memory in result["saved"]:
        _audit_memory_write("write", memory.id, tenant_id, http_request)
    return {
        "saved": [_memory_to_dict(memory) for memory in result["saved"]],
        "skipped": result["skipped"],
    }


@router.get("/export")
async def export_memories(
    user_id: str = "",
    x_tenant_id: Optional[str] = Header(default="default"),
    x_user_role: Optional[str] = Header(default="user"),
):
    """Export memories for a tenant/user as JSON (admin or own tenant)."""
    db = _require_db()
    tenant_id = (user_id or x_tenant_id or "default").strip()
    if x_user_role != "admin" and tenant_id != (x_tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权导出其他租户记忆")

    items, total = db.list_all_memories(page=1, page_size=5000, tenant_id=tenant_id)
    return {
        "tenant_id": tenant_id,
        "total": total,
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "scope": getattr(m, "scope", "private"),
                "importance": getattr(m, "importance", 0),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
    }


@router.get("/{memory_id}")
def get_memory_detail(memory_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    memory = db.get_memory(memory_id, tenant_id=x_tenant_id or "default")
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _memory_to_dict(memory)


@router.put("/{memory_id}")
def update_memory(
    memory_id: str,
    payload: UpdateMemoryRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    ok = db.update_memory(memory_id, payload.content, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("write", memory_id, tenant_id, http_request)
    memory = db.get_memory(memory_id, tenant_id=tenant_id)
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    ok = db.delete_memory(memory_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("delete", memory_id, tenant_id, http_request)
    return {"success": True}


@router.post("/{memory_id}/pin")
def pin_memory(memory_id: str, payload: PinRequest, x_tenant_id: Optional[str] = Header(default="default")):
    db = _require_db()
    ok = db.set_memory_pin(memory_id, payload.pinned, tenant_id=x_tenant_id or "default")
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"success": True, "pinned": payload.pinned}


@router.post("/{memory_id}/promote")
def promote_memory(
    memory_id: str,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    memory = db.promote_memory(memory_id, tenant_id=tenant_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("promote", memory_id, tenant_id, http_request)
    return _memory_to_dict(memory)


class ScopeUpdateRequest(BaseModel):
    scope: str = Field(pattern=r"^(private|shared)$")


@router.put("/{memory_id}/scope")
def update_memory_scope(
    memory_id: str,
    payload: ScopeUpdateRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
    x_user_role: Optional[str] = Header(default="user"),
):
    """Update memory scope (admin only)."""
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改记忆 scope")
    db = _require_db()
    tenant_id = x_tenant_id or "default"
    ok = db.set_memory_scope(memory_id, payload.scope, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("scope", memory_id, tenant_id, http_request)
    return {"success": True, "memory_id": memory_id, "scope": payload.scope}
