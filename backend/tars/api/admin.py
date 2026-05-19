"""Admin memory management REST API — v4.0.0 Phase 1 Task 9."""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from ..database import Database
from ..security.audit import safe_audit, client_ip_from_request

router = APIRouter(prefix="/api/admin", tags=["admin"])

_db: Optional[Database] = None


def init_admin_api(db: Database):
    global _db
    _db = db


def _require_admin(role: str):
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


@router.get("/memory/users")
def list_user_memory_stats(x_user_role: Optional[str] = Header(default="user")):
    """列出所有用户的记忆统计"""
    _require_admin(x_user_role)
    db = _require_db()
    conn = db._get_conn()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT tenant_id, COUNT(*) as count, "
        "SUM(CASE WHEN scope='shared' THEN 1 ELSE 0 END) as shared_count "
        "FROM memories GROUP BY tenant_id"
    ).fetchall()
    return {
        "users": [
            {"tenant_id": r[0], "memory_count": r[1], "shared_count": r[2]}
            for r in rows
        ]
    }


@router.get("/memory/users/{user_id}")
def get_user_memory_detail(
    user_id: str,
    limit: int = Query(50, le=200),
    x_user_role: Optional[str] = Header(default="user"),
):
    """查看指定用户的记忆详情"""
    _require_admin(x_user_role)
    from .memory import _memory_to_dict

    db = _require_db()
    items, total = db.list_all_memories(page=1, page_size=limit, tenant_id=user_id)
    return {
        "items": [_memory_to_dict(item) for item in items],
        "total": total,
        "tenant_id": user_id,
    }


@router.delete("/memory/users/{user_id}/purge")
def purge_user_memory(
    user_id: str,
    http_request: Request,
    x_user_role: Optional[str] = Header(default="user"),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """清空指定用户全部私有记忆"""
    _require_admin(x_user_role)
    db = _require_db()
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE tenant_id = ? AND scope = 'private'", (user_id,))
    conn.commit()
    actor_id = x_tenant_id or "default"
    safe_audit(
        lambda lg: lg.log_memory_access(
            memory_id=user_id,
            action="purge",
            tenant_id=actor_id,
            user_id=actor_id,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True, "tenant_id": user_id}


class SharedMemoryRequest(BaseModel):
    content: str
    category: str = "knowledge"


@router.post("/memory/shared")
def create_shared_memory(
    body: SharedMemoryRequest,
    http_request: Request,
    x_user_role: Optional[str] = Header(default="user"),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """创建共享记忆"""
    _require_admin(x_user_role)
    db = _require_db()
    import uuid
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    mid = str(uuid.uuid4())[:8]
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (id, tenant_id, content, category, importance, scope, created_at, updated_at, access_count, source) "
        "VALUES (?, ?, ?, ?, 0.8, 'shared', ?, ?, 0, 'admin')",
        (mid, x_tenant_id or "default", body.content, body.category, now, now),
    )
    conn.commit()
    actor_id = x_tenant_id or "default"
    safe_audit(
        lambda lg: lg.log_memory_access(
            memory_id=mid,
            action="write",
            tenant_id=actor_id,
            user_id=actor_id,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True, "id": mid, "scope": "shared"}


@router.delete("/memory/shared/{memory_id}")
def delete_shared_memory(
    memory_id: str,
    http_request: Request,
    x_user_role: Optional[str] = Header(default="user"),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """删除共享记忆"""
    _require_admin(x_user_role)
    db = _require_db()
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE id = ? AND scope = 'shared'", (memory_id,))
    conn.commit()
    actor_id = x_tenant_id or "default"
    safe_audit(
        lambda lg: lg.log_memory_access(
            memory_id=memory_id,
            action="delete",
            tenant_id=actor_id,
            user_id=actor_id,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True}
