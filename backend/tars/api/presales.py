"""售前管理 REST API — v5.0.1."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..database import Database
from ..org import ORG_ID
from ..security.audit import safe_audit, client_ip_from_request
from ._auth import Principal, require_authenticated_user, require_module

router = APIRouter(prefix="/api/presales", tags=["presales"])

_db: Optional[Database] = None


def init_presales_api(db: Database) -> None:
    global _db
    _db = db
    _ensure_tables()


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=503, detail="Presales API not initialized")
    return _db


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def _require_presales(
    principal: Principal = Depends(require_module("presales")),
) -> Principal:
    return principal


# ── 数据库初始化 ──────────────────────────────────────────

def _ensure_tables():
    db = _require_db()
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presales_projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customer_name TEXT DEFAULT '',
            industry TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            requirement_summary TEXT DEFAULT '',
            proposal_content TEXT DEFAULT '',
            ppt_outline TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_by TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            tenant_id TEXT DEFAULT 'org_default'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presales_materials (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            material_type TEXT DEFAULT 'reference',
            title TEXT DEFAULT '',
            wiki_page_name TEXT DEFAULT '',
            knowledge_doc_id TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            uploaded_by TEXT DEFAULT '',
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presales_workflows (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            workflow_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            orchestration_task_id TEXT DEFAULT '',
            input_data TEXT DEFAULT '',
            output_data TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            tenant_id TEXT DEFAULT 'org_default'
        )
    """)
    conn.commit()


# ── 请求/响应模型 ────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    customer_name: str = ""
    industry: str = ""
    tags: list[str] = []


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    customer_name: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    requirement_summary: Optional[str] = None
    proposal_content: Optional[str] = None
    ppt_outline: Optional[str] = None
    tags: Optional[list[str]] = None


class AddMaterialRequest(BaseModel):
    material_type: str = "reference"
    title: str = ""
    wiki_page_name: str = ""
    knowledge_doc_id: str = ""
    file_path: str = ""


class StartWorkflowRequest(BaseModel):
    workflow_type: str = Field(..., description="requirement_research / proposal_generation / ppt_generation")
    input_data: str = ""


class GenerateRequest(BaseModel):
    project_id: str
    context: str = ""


# ── 项目 CRUD ───────────────────────────────────────────

@router.get("/projects")
def list_projects(
    principal: Principal = Depends(_require_presales),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    db = _require_db()
    conn = db._get_conn()
    tenant_id = ORG_ID

    where = ["tenant_id = ?"]
    params = [tenant_id]
    if status:
        where.append("status = ?")
        params.append(status)

    count_sql = f"SELECT COUNT(*) FROM presales_projects WHERE {' AND '.join(where)}"
    total = conn.cursor().execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    sql = f"SELECT id, name, customer_name, industry, status, requirement_summary, proposal_content, ppt_outline, tags, created_by, created_at, updated_at, tenant_id FROM presales_projects WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    rows = conn.cursor().execute(sql, params + [page_size, offset]).fetchall()

    projects = []
    for r in rows:
        projects.append({
            "id": r[0], "name": r[1], "customer_name": r[2],
            "industry": r[3], "status": r[4],
            "requirement_summary": r[5], "proposal_content": r[6],
            "ppt_outline": r[7], "tags": json.loads(r[8] or "[]"),
            "created_by": r[9], "created_at": r[10],
            "updated_at": r[11], "tenant_id": r[12],
        })

    return {"projects": projects, "total": total, "page": page, "page_size": page_size}


@router.post("/projects")
def create_project(
    body: CreateProjectRequest,
    request: Request,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()
    project_id = str(uuid.uuid4())
    now = _now()

    conn.cursor().execute(
        "INSERT INTO presales_projects (id, name, customer_name, industry, status, tags, created_by, created_at, updated_at, tenant_id) "
        "VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)",
        (project_id, body.name, body.customer_name, body.industry,
         json.dumps(body.tags, ensure_ascii=False),
         principal.user_id, now, now, ORG_ID),
    )
    conn.commit()

    safe_audit(
        lambda lg: lg.log_user_event(
            action="presales_project_create",
            target_user_id=principal.user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"project_id={project_id},name={body.name}",
            client_ip=client_ip_from_request(request),
        )
    )

    return {"success": True, "id": project_id}


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()
    row = conn.cursor().execute(
        "SELECT id, name, customer_name, industry, status, requirement_summary, proposal_content, ppt_outline, tags, created_by, created_at, updated_at, tenant_id FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (project_id, ORG_ID),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "id": row[0], "name": row[1], "customer_name": row[2],
        "industry": row[3], "status": row[4],
        "requirement_summary": row[5], "proposal_content": row[6],
        "ppt_outline": row[7], "tags": json.loads(row[8] or "[]"),
        "created_by": row[9], "created_at": row[10],
        "updated_at": row[11], "tenant_id": row[12],
    }


@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    request: Request,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()

    existing = conn.cursor().execute(
        "SELECT id FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (project_id, ORG_ID),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    updates = []
    params = []
    for field in ("name", "customer_name", "industry", "status",
                  "requirement_summary", "proposal_content", "ppt_outline"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)

    if body.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(body.tags, ensure_ascii=False))

    if updates:
        updates.append("updated_at = ?")
        params.append(_now())
        params.append(project_id)
        conn.cursor().execute(
            f"UPDATE presales_projects SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    safe_audit(
        lambda lg: lg.log_user_event(
            action="presales_project_update",
            target_user_id=principal.user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"project_id={project_id}",
            client_ip=client_ip_from_request(request),
        )
    )

    return {"success": True}


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    request: Request,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()

    existing = conn.cursor().execute(
        "SELECT id FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (project_id, ORG_ID),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    conn.cursor().execute("DELETE FROM presales_materials WHERE project_id = ?", (project_id,))
    conn.cursor().execute("DELETE FROM presales_workflows WHERE project_id = ?", (project_id,))
    conn.cursor().execute("DELETE FROM presales_projects WHERE id = ?", (project_id,))
    conn.commit()

    safe_audit(
        lambda lg: lg.log_user_event(
            action="presales_project_delete",
            target_user_id=principal.user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"project_id={project_id}",
            client_ip=client_ip_from_request(request),
        )
    )

    return {"success": True}


# ── 材料管理 ─────────────────────────────────────────────

@router.get("/projects/{project_id}/materials")
def list_materials(
    project_id: str,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()
    rows = conn.cursor().execute(
        "SELECT id, project_id, material_type, title, wiki_page_name, knowledge_doc_id, file_path, uploaded_by, created_at FROM presales_materials WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    return {
        "materials": [
            {"id": r[0], "project_id": r[1], "material_type": r[2],
             "title": r[3], "wiki_page_name": r[4],
             "knowledge_doc_id": r[5], "file_path": r[6],
             "uploaded_by": r[7], "created_at": r[8]}
            for r in rows
        ]
    }


@router.post("/projects/{project_id}/materials")
def add_material(
    project_id: str,
    body: AddMaterialRequest,
    request: Request,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()

    existing = conn.cursor().execute(
        "SELECT id FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (project_id, ORG_ID),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    mat_id = str(uuid.uuid4())
    now = _now()
    conn.cursor().execute(
        "INSERT INTO presales_materials (id, project_id, material_type, title, wiki_page_name, knowledge_doc_id, file_path, uploaded_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mat_id, project_id, body.material_type, body.title,
         body.wiki_page_name, body.knowledge_doc_id, body.file_path,
         principal.user_id, now),
    )
    conn.commit()

    safe_audit(
        lambda lg: lg.log_user_event(
            action="presales_material_add",
            target_user_id=principal.user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"project_id={project_id},material_id={mat_id}",
            client_ip=client_ip_from_request(request),
        )
    )

    return {"success": True, "id": mat_id}


# ── 工作流 ───────────────────────────────────────────────

@router.post("/workflows")
def start_workflow(
    body: StartWorkflowRequest,
    request: Request,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()
    wf_id = str(uuid.uuid4())
    now = _now()

    conn.cursor().execute(
        "INSERT INTO presales_workflows (id, project_id, workflow_type, status, input_data, created_by, created_at, updated_at, tenant_id) "
        "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
        (wf_id, "", body.workflow_type, body.input_data,
         principal.user_id, now, now, ORG_ID),
    )
    conn.commit()

    safe_audit(
        lambda lg: lg.log_user_event(
            action="presales_workflow_start",
            target_user_id=principal.user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"workflow_id={wf_id},type={body.workflow_type}",
            client_ip=client_ip_from_request(request),
        )
    )

    return {"success": True, "id": wf_id, "status": "pending"}


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    principal: Principal = Depends(_require_presales),
):
    db = _require_db()
    conn = db._get_conn()
    row = conn.cursor().execute(
        "SELECT id, project_id, workflow_type, status, orchestration_task_id, input_data, output_data, created_by, created_at, updated_at, tenant_id FROM presales_workflows WHERE id = ?",
        (workflow_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="工作流不存在")

    return {
        "id": row[0], "project_id": row[1], "workflow_type": row[2],
        "status": row[3], "orchestration_task_id": row[4],
        "input_data": row[5], "output_data": row[6],
        "created_by": row[7], "created_at": row[8],
        "updated_at": row[9], "tenant_id": row[10],
    }


# ── AI 生成 ──────────────────────────────────────────────

@router.post("/generate/proposal")
def generate_proposal(
    body: GenerateRequest,
    principal: Principal = Depends(_require_presales),
):
    """AI 生成方案文档（返回结构化方案草稿）。"""
    db = _require_db()
    conn = db._get_conn()
    existing = conn.cursor().execute(
        "SELECT requirement_summary FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (body.project_id, ORG_ID),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 提示：方案生成由 LLM Agent 在对话中完成。
    # 此端点返回引导信息，前端应在对话中触发 doc_writer 技能。
    return {
        "success": True,
        "project_id": body.project_id,
        "message": "请在对话中发送「为项目 xxx 生成技术方案」，系统将自动激活方案撰写技能。",
    }


@router.post("/generate/ppt")
def generate_ppt(
    body: GenerateRequest,
    principal: Principal = Depends(_require_presales),
):
    """AI 生成 PPT 大纲（返回结构化大纲）。"""
    db = _require_db()
    conn = db._get_conn()
    existing = conn.cursor().execute(
        "SELECT proposal_content FROM presales_projects WHERE id = ? AND tenant_id = ?",
        (body.project_id, ORG_ID),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "success": True,
        "project_id": body.project_id,
        "message": "请在对话中发送「为项目 xxx 生成汇报PPT」，系统将自动激活PPT生成技能。",
    }
