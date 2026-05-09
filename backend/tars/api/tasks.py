"""v2.4 任务自动化 API — /api/tasks/"""
import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List


router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 模块级引用，由 init_tasks_api 设置
db = None
agent = None


def init_tasks_api(database, agent_instance):
    global db, agent
    db = database
    agent = agent_instance


def _now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


# ========= Pydantic 模型 =========

class TaskCreateRequest(BaseModel):
    goal: str
    title: Optional[str] = None
    workspace_path: Optional[str] = None
    steps: Optional[List[dict]] = None


class TaskResponse(BaseModel):
    id: str
    session_id: str
    title: str
    goal: str
    workspace_path: str
    workspace_source: str
    status: str
    current_step: int
    total_steps: int
    artifacts: Optional[list] = None
    output_summary: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    steps: list = []


def _task_to_dict(row, steps_rows=None):
    return {
        "id": row[0], "session_id": row[1], "title": row[2], "goal": row[3],
        "workspace_path": row[4], "workspace_source": row[5],
        "status": row[6], "current_step": row[7], "total_steps": row[8],
        "artifacts": json.loads(row[9]) if row[9] else None,
        "output_summary": row[10],
        "created_at": row[11], "updated_at": row[12],
        "completed_at": row[13], "error_message": row[14],
        "steps": [_step_to_dict(s) for s in (steps_rows or [])],
    }


def _step_to_dict(row):
    return {
        "id": row[0], "task_id": row[1], "step_order": row[2],
        "description": row[3], "tool": row[4],
        "arguments": json.loads(row[5]) if row[5] else {},
        "verify_type": row[6], "verify_expected": row[7], "verify_msg": row[8],
        "expected_artifacts": json.loads(row[9]) if row[9] else None,
        "status": row[10], "result": row[11], "error": row[12],
        "retries": row[13], "started_at": row[14], "completed_at": row[15],
    }


# ========= 端点 =========

@router.get("/")
async def list_tasks(session_id: Optional[str] = None):
    conn = db._get_conn()
    cur = conn.cursor()
    if session_id:
        cur.execute("SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at DESC", (session_id,))
    else:
        cur.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50")
    tasks = []
    for row in cur.fetchall():
        cur.execute("SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_order", (row[0],))
        steps = cur.fetchall()
        tasks.append(_task_to_dict(row, steps))
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/")
async def create_task(request: TaskCreateRequest):
    if not db or not agent:
        raise HTTPException(status_code=503, detail="服务未就绪")

    task_id = str(uuid.uuid4())
    session_id = getattr(agent, "_current_session_id", "default")
    title = request.title or request.goal[:30]
    now = _now_iso()

    # Workspace 路径解析
    from tars.orchestration.workspace_resolver import resolve_workspace_path
    ws_path, ws_source = resolve_workspace_path(session_id, request.workspace_path, title)

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (task_id, session_id, title, request.goal, ws_path, ws_source,
         "pending", 0, len(request.steps or []), None, None,
         now, now, None, None),
    )

    # 写入步骤
    if request.steps:
        for s in request.steps:
            cur.execute(
                "INSERT INTO task_steps(task_id,step_order,description,tool,arguments,"
                "verify_type,verify_expected,verify_msg,expected_artifacts) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (task_id, s.get("id", 0), s.get("description", ""),
                 s.get("tool", ""), json.dumps(s.get("arguments", {})),
                 s.get("verify", {}).get("type"),
                 s.get("verify", {}).get("expected"),
                 s.get("verify", {}).get("error_msg"),
                 json.dumps(s.get("expected_artifacts", [])),
                 ),
            )

    conn.commit()
    return {"success": True, "task_id": task_id, "workspace_path": ws_path, "workspace_source": ws_source}


@router.get("/{task_id}")
async def get_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    cur.execute("SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_order", (task_id,))
    steps = cur.fetchall()
    return _task_to_dict(row, steps)


@router.post("/{task_id}/confirm")
async def confirm_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ?", (_now_iso(), task_id))
    conn.commit()
    return {"success": True, "message": "任务已确认执行"}


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'paused', updated_at = ? WHERE id = ? AND status = 'running'",
                (_now_iso(), task_id))
    conn.commit()
    return {"success": True, "message": "任务已暂停"}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ? AND status = 'paused'",
                (_now_iso(), task_id))
    conn.commit()
    return {"success": True, "message": "任务已恢复"}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'aborted', updated_at = ?, completed_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), task_id))
    conn.commit()
    return {"success": True, "message": "任务已取消"}


# ========= v2.5 权限查询 =========

@router.get("/skills/{skill_id}/permissions")
async def get_skill_permissions(skill_id: str):
    from ..skills.permission_engine import permission_engine
    declared = permission_engine.get_declared_permissions(skill_id)
    granted = permission_engine.get_skill_permissions(skill_id)
    return {
        "skill_id": skill_id,
        "declared": sorted(declared),
        "granted": sorted(granted),
    }


@router.post("/{task_id}/retry")
async def retry_task(task_id: str):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'pending', current_step = 0, updated_at = ?, completed_at = NULL, error_message = NULL WHERE id = ?",
                (_now_iso(), task_id))
    cur.execute("UPDATE task_steps SET status = 'pending', result = NULL, error = NULL, retries = 0, started_at = NULL, completed_at = NULL WHERE task_id = ?",
                (task_id,))
    conn.commit()
    return {"success": True, "message": "任务已重置，可重新执行"}
