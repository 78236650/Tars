"""Sessions REST API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..database import Database

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
def list_sessions():
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return [_session_to_dict(s) for s in _db.list_sessions()]


@router.post("/")
def create_session():
    if not _db:
        raise HTTPException(500, "DB not initialized")
    s = _db.create_session(title="New Chat")
    return _session_to_dict(s)


@router.get("/{session_id}/messages")
def get_session_messages(session_id: str):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    if not _db.get_session(session_id):
        raise HTTPException(404, "Session not found")
    return [_message_to_dict(m) for m in _db.get_messages(session_id)]


@router.delete("/{session_id}")
def delete_session(session_id: str):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}


@router.patch("/{session_id}")
def update_session_title(session_id: str, payload: TitleUpdateRequest):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.update_session_title(session_id, payload.title)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}
