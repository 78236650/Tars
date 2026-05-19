"""Audit log query REST API — v4.0.0 Phase 1 Task 4.

Provides: GET /api/audit/logs — query audit log entries (admin only).
"""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query

from ..database import Database
from ..security.audit import init_audit_logger, audit_logger as _audit_logger

router = APIRouter(prefix="/api/audit", tags=["audit"])

_db: Optional[Database] = None


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


@router.get("/logs")
def list_audit_logs(
    action: str = Query(""),
    user_id: str = Query(""),
    resource_type: str = Query(""),
    tenant_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    x_user_role: Optional[str] = Header(default="user"),
):
    """Query audit log entries. Requires admin role."""
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查询审计日志")
    db = _require_db()
    logs, total = db.list_audit_logs(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
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
