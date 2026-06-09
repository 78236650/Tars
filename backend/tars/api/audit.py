"""Audit log query REST API — v4.0.0 Phase 1 Task 4."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database
from ..security.audit import init_audit_logger, audit_logger as _audit_logger
from ._auth import Principal, require_admin

router = APIRouter(prefix="/api/audit", tags=["audit"])

_db: Optional[Database] = None

ACTION_GROUPS: dict[str, List[str]] = {
    "skill": ["skill_install", "skill_uninstall"],
    "tool": ["tool_call", "tool_call:success", "tool_call:failed", "permission_denied"],
    "bi": ["bi_query"],
    "auth": ["login", "logout"],
    "memory": ["memory:write", "memory:delete", "memory:promote", "memory:purge"],
    "provider": ["model_fallback"],
}


def init_audit_api(db: Database):
    """Initialize audit API; called from main.py startup."""
    global _db
    _db = db
    init_audit_logger(db)


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


def _format_resource(log) -> str:
    if log.resource_id:
        return f"{log.resource_type}:{log.resource_id}"
    return log.resource_type or ""


@router.get("/decisions")
def list_agent_decisions(
    trace_id: str = Query("", max_length=128),
    session_id: str = Query("", max_length=128),
    decision_type: str = Query("", max_length=64),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_admin),
):
    """查询 Agent 决策链(v5.0.5/A6)。

    按 trace_id 可回放一次请求的完整决策序列(技能路由→记忆检索→升格等)。
    需 admin。至少应提供 trace_id 或 session_id 之一以缩小范围。
    """
    db = _require_db()
    if not trace_id and not session_id and not decision_type:
        raise HTTPException(status_code=400, detail="请至少提供 trace_id 或 session_id")
    from ..agent.decision_trace import query_decisions

    rows = query_decisions(
        db,
        trace_id=trace_id,
        session_id=session_id,
        decision_type=decision_type,
        limit=limit,
    )
    return {"success": True, "count": len(rows), "decisions": rows}


@router.get("/logs")
def list_audit_logs(
    action: str = Query("", max_length=255),
    action_group: str = Query("", max_length=64),
    user_id: str = Query("", max_length=255),
    resource_type: str = Query("", max_length=128),
    tenant_id: str = Query("", max_length=255),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_admin),
):
    """Query audit log entries. Requires admin role."""
    db = _require_db()

    actions_filter: Optional[List[str]] = None
    if action_group:
        actions_filter = ACTION_GROUPS.get(action_group)
        if actions_filter is None:
            raise HTTPException(status_code=400, detail=f"未知 action_group: {action_group}")

    logs, total = db.list_audit_logs(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        actions=actions_filter,
        resource_type=resource_type,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            {
                "id": log.id,
                "tenant_id": log.tenant_id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource": _format_resource(log),
                "detail": log.detail,
                "client_ip": log.client_ip,
                "ip_address": log.client_ip,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
