"""Sessions REST API"""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..database import Database
from ..security.audit import safe_audit, client_ip_from_request

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_db: Optional[Database] = None


def init_sessions_api(db: Database):
    global _db
    _db = db


class TitleUpdateRequest(BaseModel):
    title: str


def _session_to_dict(s):
    return {
        "id": s.id,
        "title": s.title,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m):
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
    }


@router.get("/")
def list_sessions(x_tenant_id: Optional[str] = Header(default="default")):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return [_session_to_dict(s) for s in _db.list_sessions(tenant_id=x_tenant_id or "default")]


@router.post("/")
def create_session(
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    tenant_id = x_tenant_id or "default"
    s = _db.create_session(title="New Chat", tenant_id=tenant_id)
    safe_audit(
        lambda lg: lg.log_session_event(
            action="session_create",
            session_id=s.id,
            tenant_id=tenant_id,
            user_id=tenant_id,
            detail=s.title,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return _session_to_dict(s)


@router.get("/{session_id}/messages")
def get_session_messages(session_id: str, x_tenant_id: Optional[str] = Header(default="default")):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    tenant_id = x_tenant_id or "default"
    if not _db.get_session(session_id, tenant_id=tenant_id):
        raise HTTPException(404, "Session not found")
    return [_message_to_dict(m) for m in _db.get_messages(session_id)]


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    tenant_id = x_tenant_id or "default"
    ok = _db.delete_session(session_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    safe_audit(
        lambda lg: lg.log_session_event(
            action="session_delete",
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=tenant_id,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True}


@router.patch("/{session_id}")
def update_session_title(
    session_id: str,
    payload: TitleUpdateRequest,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.update_session_title(session_id, payload.title, tenant_id=x_tenant_id or "default")
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True, "title": payload.title}
