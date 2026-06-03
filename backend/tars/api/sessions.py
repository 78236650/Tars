"""Sessions REST API"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..api._auth import Principal, require_authenticated_user
from ..database import Database
from ..org import ORG_ID
from ..orchestration.artifacts_collector import ArtifactsCollector
from ..orchestration.workspace_resolver import resolve_workspace_path
from ..security.audit import safe_audit, client_ip_from_request

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_db: Database | None = None


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
def list_sessions(principal: Principal = Depends(require_authenticated_user)):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return [
        _session_to_dict(s)
        for s in _db.list_sessions(user_id=principal.user_id, tenant_id=ORG_ID)
    ]


@router.post("/")
def create_session(
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    s = _db.create_session(
        user_id=principal.user_id,
        title="New Chat",
        tenant_id=ORG_ID,
    )
    safe_audit(
        lambda lg: lg.log_session_event(
            action="session_create",
            session_id=s.id,
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            detail=s.title,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return _session_to_dict(s)


@router.get("/{session_id}/messages")
def get_session_messages(
    session_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    if not _db.get_session(session_id, tenant_id=ORG_ID, user_id=principal.user_id):
        raise HTTPException(404, "Session not found")
    return [_message_to_dict(m) for m in _db.get_messages(session_id)]


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    http_request: Request,
    principal: Principal = Depends(require_authenticated_user),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.delete_session(session_id, tenant_id=ORG_ID, user_id=principal.user_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    safe_audit(
        lambda lg: lg.log_session_event(
            action="session_delete",
            session_id=session_id,
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True}


@router.patch("/{session_id}")
def update_session_title(
    session_id: str,
    payload: TitleUpdateRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.update_session_title(
        session_id,
        payload.title,
        tenant_id=ORG_ID,
        user_id=principal.user_id,
    )
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True, "title": payload.title}


def _artifact_directory(relative_path: str) -> str:
    parent = Path(relative_path).parent
    if str(parent) == ".":
        return "/"
    return str(parent)


def _list_workspace_artifacts(workspace_path: str) -> list[dict]:
    root = Path(workspace_path)
    if not root.exists():
        return []
    items: list[dict] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or ArtifactsCollector._is_excluded(file_path):
            continue
        rel = str(file_path.relative_to(root))
        items.append({
            "path": rel,
            "directory": _artifact_directory(rel),
            "name": file_path.name,
            "source": "workspace",
        })
    return items


@router.get("/{session_id}/artifacts")
def get_session_artifacts(
    session_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    if not _db.get_session(session_id, tenant_id=ORG_ID, user_id=principal.user_id):
        raise HTTPException(404, "Session not found")

    workspace_path, workspace_source = resolve_workspace_path(session_id)
    workspace_files = _list_workspace_artifacts(workspace_path)

    conn = _db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, goal, workspace_path, status, artifacts, output_summary "
        "FROM tasks WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,),
    )

    tasks: list[dict] = []
    seen_paths: set[str] = set()
    items: list[dict] = []

    for row in cur.fetchall():
        raw_artifacts = json.loads(row[5]) if row[5] else []
        artifacts = raw_artifacts if isinstance(raw_artifacts, list) else []
        task_workspace = row[3] or workspace_path
        task = {
            "id": row[0],
            "title": row[1],
            "goal": row[2],
            "workspace_path": task_workspace,
            "status": row[4],
            "artifacts": artifacts,
            "output_summary": row[6],
        }
        tasks.append(task)
        for art in artifacts:
            if not isinstance(art, str) or not art.strip():
                continue
            rel = art.strip()
            if rel in seen_paths:
                continue
            seen_paths.add(rel)
            items.append({
                "path": rel,
                "directory": _artifact_directory(rel),
                "name": Path(rel).name,
                "source": "task",
                "task_id": row[0],
                "task_title": row[1],
                "workspace_path": task_workspace,
            })

    for file_item in workspace_files:
        if file_item["path"] in seen_paths:
            continue
        seen_paths.add(file_item["path"])
        items.append({
            **file_item,
            "workspace_path": workspace_path,
        })

    items.sort(key=lambda x: (x.get("directory", ""), x.get("path", "")))

    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "workspace_path": workspace_path,
            "workspace_source": workspace_source,
            "tasks": tasks,
            "items": items,
            "total": len(items),
        },
    }
