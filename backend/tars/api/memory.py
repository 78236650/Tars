"""Memory management REST API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..database import Database
from ..config.memory import config
from ..memory.compressor import MemoryCompressor
from ..memory.core_memory import BLOCK_NAMES
from ..memory.manager import MemoryManager
from ..memory.tree_builder import EntityTreeBuilder
from ..security.audit import safe_audit, client_ip_from_request
from ..context import get_current_user_id, set_request_context
from ..org import ORG_ID
from ._auth import Principal, require_authenticated_user

router = APIRouter(prefix="/api/memory", tags=["memory"])

_db: Optional[Database] = None
_memory_manager: Optional[MemoryManager] = None
_compressor: Optional[MemoryCompressor] = None
_provider_resolver = None


def init_memory_api(db: Database, memory_manager: MemoryManager):
    global _db, _memory_manager, _compressor
    _db = db
    _memory_manager = memory_manager
    _compressor = memory_manager.compressor


def set_memory_provider_resolver(resolver):
    """Lazy-resolve LLM provider for extract-from-turn when manager has none."""
    global _provider_resolver
    _provider_resolver = resolver


def _resolve_provider(manager: MemoryManager):
    if manager.provider:
        return manager.provider
    if _provider_resolver:
        try:
            return _provider_resolver()
        except Exception:
            return None
    return None


def _org_manager() -> MemoryManager:
    return _require_manager().for_tenant(ORG_ID)


def _manager_with_provider() -> MemoryManager:
    manager = _org_manager()
    provider = _resolve_provider(manager)
    if provider and not manager.provider:
        manager.set_provider(provider)
    return manager


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


def _org_compressor() -> MemoryCompressor:
    base = _require_compressor()
    return MemoryCompressor(base.db, provider=base.provider, tenant_id=ORG_ID)


def _audit_memory_write(
    action: str,
    memory_id: str,
    principal: Principal,
    http_request: Optional[Request] = None,
):
    safe_audit(
        lambda lg: lg.log_memory_access(
            memory_id=memory_id,
            action=action,
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            client_ip=client_ip_from_request(http_request),
        )
    )


def _viewer_user_id() -> str:
    """Authenticated user for per-user private memory visibility."""
    return get_current_user_id()


def _apply_admin_view_user(principal: Principal, user_id: str) -> None:
    """Admin may pass user_id to view another user's tree/core; sets context for repo."""
    target = (user_id or "").strip() or principal.user_id
    if target != principal.user_id and not principal.is_admin:
        raise HTTPException(status_code=403, detail="无权查看其他用户记忆")
    if target != get_current_user_id():
        set_request_context(target, ORG_ID)


def _resolve_tree_tenant(principal: Principal, user_id: str = "") -> str:
    """Resolve org tree scope; admin may pass user_id to view another user's memories."""
    _apply_admin_view_user(principal, user_id)
    return ORG_ID


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
    content: str = Field(default="", max_length=10000)


class UpdateMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100000)


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
    user_context: str = Field(default="", max_length=8000)
    publish_to_knowledge: bool = False
    promotion_group_id: Optional[str] = Field(default=None, max_length=128)


class PromoteToKnowledgeRequest(BaseModel):
    promotion_group_id: Optional[str] = None
    memory_ids: Optional[List[str]] = None
    user_context: str = Field(default="", max_length=8000)


@router.get("/stats")
def get_memory_stats(principal: Principal = Depends(require_authenticated_user)):
    db = _require_db()
    stats = db.get_memory_stats(tenant_id=ORG_ID, user_id=_viewer_user_id())
    if config.compressor_enabled:
        compressor = _require_compressor()
        status = compressor.status()
        stats["last_compressed_at"] = status.get("last_finished_at")
    return stats


@router.get("/core")
def get_core_memory(principal: Principal = Depends(require_authenticated_user)):
    manager = _org_manager()
    return {"blocks": manager.core.get_all(), "tenant_id": ORG_ID, "user_id": principal.user_id}


@router.put("/core/{block}")
def update_core_memory(
    block: str,
    payload: UpdateCoreBlockRequest,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    manager = _org_manager()
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
        "tenant_id": ORG_ID,
        "user_id": principal.user_id,
    }


@router.get("/recent")
def get_recent_memories(
    page: int = 1,
    q: str = "",
    cat: str = "",
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    items, total = db.list_recent_memories(
        page=page, query=q, category=cat, tenant_id=ORG_ID, user_id=_viewer_user_id()
    )
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
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    memories, total = db.list_longterm_memories(
        tenant_id=ORG_ID, page=page, page_size=20, user_id=_viewer_user_id()
    )

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
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    items, total = db.list_all_memories(
        page=page,
        query=q,
        category=cat,
        memory_type=memory_type,
        tenant_id=ORG_ID,
        user_id=_viewer_user_id(),
    )
    return {
        "items": [_memory_to_dict(item) for item in items],
        "page": page,
        "page_size": 20,
        "total": total,
    }


@router.get("/compress/status")
def get_compress_status():
    if not config.compressor_enabled:
        return {"enabled": False}
    compressor = _require_compressor()
    return compressor.status()


@router.post("/compress")
async def run_manual_compress(principal: Principal = Depends(require_authenticated_user)):
    if not config.compressor_enabled:
        raise HTTPException(status_code=403, detail="Memory compressor disabled in vertical mode")
    compressor = _org_compressor()
    report = await compressor.compress_all()
    _require_compressor()._status = compressor._status
    return report


@router.post("/merge")
async def merge_memories(
    payload: MergeRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    if not config.compressor_enabled:
        raise HTTPException(status_code=403, detail="Memory compressor disabled in vertical mode")
    compressor = _org_compressor()
    try:
        return await compressor.merge_memories(payload.memory_ids, preview_only=payload.preview_only)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/extract-from-turn")
async def extract_memories_from_turn(
    payload: ExtractTurnRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    manager = _manager_with_provider()
    items = await manager.extract_turn_memories(payload.user_content, payload.assistant_content)
    return {"items": items}


@router.post("/save-from-turn")
async def save_memories_from_turn(
    payload: SaveTurnMemoriesRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    manager = _manager_with_provider()
    allowed = {"fact", "preference", "decision", "domain_knowledge"}
    for item in payload.items:
        if item.category not in allowed:
            raise HTTPException(status_code=400, detail=f"invalid category: {item.category}")

    result = await manager.save_turn_memories(
        [item.model_dump() for item in payload.items],
        user_context=payload.user_context,
        publish_to_knowledge=payload.publish_to_knowledge,
        promotion_group_id=payload.promotion_group_id,
    )
    for memory in result["saved"]:
        _audit_memory_write("write", memory.id, principal, http_request)

    group_id = result.get("promotion_group_id")
    if (
        config.kb_promotion_enabled
        and group_id
        and not payload.publish_to_knowledge
        and result.get("saved")
    ):
        background_tasks.add_task(_background_kb_promotion_check, group_id)

    return {
        "saved": [_memory_to_dict(memory) for memory in result["saved"]],
        "skipped": result["skipped"],
        "knowledge_doc_ids": result.get("knowledge_doc_ids") or [],
        "promotion_group_id": group_id,
        "promotion_trigger": result.get("promotion_trigger", "none"),
    }


async def _background_kb_promotion_check(group_id: str) -> None:
    """保存后后台阈值检查（非 cron）。"""
    if not config.kb_promotion_enabled:
        return
    try:
        manager = _manager_with_provider()
        from ..memory.kb_promotion import maybe_auto_promote_group

        doc_id = await maybe_auto_promote_group(manager, group_id)
        if doc_id:
            print(f"[MemoryAPI] Auto-promoted group {group_id} -> KB doc {doc_id}")
    except Exception as e:
        print(f"[MemoryAPI] Background KB promotion failed: {e}")


@router.post("/promote-to-knowledge")
async def promote_memories_to_knowledge(
    payload: PromoteToKnowledgeRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    """手动将 pending 记忆组合成一篇知识库文档。"""
    if not config.kb_promotion_enabled:
        raise HTTPException(status_code=403, detail="KB promotion disabled in vertical mode")
    manager = _manager_with_provider()
    from ..memory.kb_promotion import default_promotion_group_id, promote_group_to_kb

    group_id = payload.promotion_group_id or default_promotion_group_id(manager.tenant_id)
    doc_id = await promote_group_to_kb(
        manager,
        group_id,
        user_context=payload.user_context,
        memory_ids=payload.memory_ids,
    )
    if not doc_id:
        raise HTTPException(status_code=404, detail="没有可升格的记忆，或知识库组件不可用")
    return {
        "success": True,
        "knowledge_doc_id": doc_id,
        "promotion_group_id": group_id,
    }




@router.get("/tree")
def get_memory_tree(
    view: str = "entity",
    max_per_bucket: int = 30,
    include_core: bool = True,
    include_orphan: bool = True,
    user_id: str = "",
    principal: Principal = Depends(require_authenticated_user),
):
    if not config.tree_builder_enabled:
        raise HTTPException(status_code=403, detail="Memory tree builder disabled in vertical mode")
    if view not in ("entity", "provenance"):
        raise HTTPException(status_code=400, detail="unsupported view")
    _apply_admin_view_user(principal, user_id)
    builder = EntityTreeBuilder(_require_db(), tenant_id=ORG_ID, max_per_bucket=max_per_bucket)
    if view == "provenance":
        return builder.build_provenance()
    return builder.build(include_core=include_core, include_orphan=include_orphan)


@router.get("/tree/search")
def search_memory_tree(
    q: str = "",
    limit: int = 20,
    view: str = "entity",
    user_id: str = "",
    principal: Principal = Depends(require_authenticated_user),
):
    if not config.tree_builder_enabled:
        raise HTTPException(status_code=403, detail="Memory tree builder disabled in vertical mode")
    if view not in ("entity", "provenance"):
        raise HTTPException(status_code=400, detail="unsupported view")
    _apply_admin_view_user(principal, user_id)
    builder = EntityTreeBuilder(_require_db(), tenant_id=ORG_ID)
    return builder.search(q, limit=min(max(limit, 1), 50), view=view)


@router.get("/tree/graph")
def get_memory_tree_graph(
    user_id: str = "",
    max_edges: int = 800,
    principal: Principal = Depends(require_authenticated_user),
):
    if not config.tree_builder_enabled:
        raise HTTPException(status_code=403, detail="Memory tree builder disabled in vertical mode")
    _apply_admin_view_user(principal, user_id)
    builder = EntityTreeBuilder(_require_db(), tenant_id=ORG_ID)
    return builder.build_graph(max_edges=min(max(max_edges, 1), 2000))


@router.get("/tree/relations")
def get_memory_tree_relations(
    entity_id: str,
    user_id: str = "",
    principal: Principal = Depends(require_authenticated_user),
):
    if not config.tree_builder_enabled:
        raise HTTPException(status_code=403, detail="Memory tree builder disabled in vertical mode")
    if not entity_id.strip():
        raise HTTPException(status_code=400, detail="entity_id required")
    _apply_admin_view_user(principal, user_id)
    builder = EntityTreeBuilder(_require_db(), tenant_id=ORG_ID)
    return builder.get_relations(entity_id.strip())


@router.get("/export")
async def export_memories(
    user_id: str = "",
    format: str = Query("json", description="Export format: 'json' or 'markdown'"),
    principal: Principal = Depends(require_authenticated_user),
):
    """Export org memories as JSON or Markdown."""
    db = _require_db()
    requested = (user_id or principal.user_id).strip()
    if not principal.is_admin and requested != principal.user_id:
        raise HTTPException(status_code=403, detail="无权导出其他用户记忆")

    if format == "markdown":
        manager = _manager_with_provider()
        md = manager.export_markdown()
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8")

    items, total = db.list_all_memories(page=1, page_size=5000, tenant_id=ORG_ID)
    return {
        "org_id": ORG_ID,
        "user_id": requested,
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


class MemoryImportRequest(BaseModel):
    markdown: str = Field(..., max_length=5 * 1024 * 1024, description="Markdown text to import")


@router.post("/import")
async def import_memories(
    payload: MemoryImportRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    """Import memories from a Markdown document.

    Parses `## 长期记忆` section with `- [category] content` bullets.
    """
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可导入记忆")
    manager = _manager_with_provider()
    result = manager.import_markdown(payload.markdown)
    return {"success": True, **result}


@router.get("/{memory_id}")
def get_memory_detail(
    memory_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    memory = db.get_memory(memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id())
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _memory_to_dict(memory)


@router.put("/{memory_id}")
def update_memory(
    memory_id: str,
    payload: UpdateMemoryRequest,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    if db.get_memory(memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id()) is None:
        raise HTTPException(status_code=404, detail="memory not found")
    ok = db.update_memory(memory_id, payload.content, tenant_id=ORG_ID)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("write", memory_id, principal, http_request)
    memory = db.get_memory(memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id())
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    if db.get_memory(memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id()) is None:
        raise HTTPException(status_code=404, detail="memory not found")
    ok = db.delete_memory(memory_id, tenant_id=ORG_ID)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("delete", memory_id, principal, http_request)
    return {"success": True}


@router.post("/{memory_id}/pin")
def pin_memory(
    memory_id: str,
    payload: PinRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    if db.get_memory(memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id()) is None:
        raise HTTPException(status_code=404, detail="memory not found")
    ok = db.set_memory_pin(memory_id, payload.pinned, tenant_id=ORG_ID)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"success": True, "pinned": payload.pinned}


@router.post("/{memory_id}/promote")
def promote_memory(
    memory_id: str,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    db = _require_db()
    memory = db.promote_memory(
        memory_id, tenant_id=ORG_ID, user_id=_viewer_user_id()
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("promote", memory_id, principal, http_request)
    return _memory_to_dict(memory)


class ScopeUpdateRequest(BaseModel):
    scope: str = Field(pattern=r"^(private|shared)$")


@router.put("/{memory_id}/scope")
def update_memory_scope(
    memory_id: str,
    payload: ScopeUpdateRequest,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    """Update memory scope (admin only)."""
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可修改记忆 scope")
    db = _require_db()
    ok = db.set_memory_scope(memory_id, payload.scope, tenant_id=ORG_ID)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit_memory_write("scope", memory_id, principal, http_request)
    return {"success": True, "memory_id": memory_id, "scope": payload.scope}
