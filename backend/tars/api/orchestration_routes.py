"""Orchestration task REST API — v4.4.0."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import Database
from ..orchestration.orchestration_memory import OrchestrationMemory
from ..orchestration.multi_agent_orchestrator import MultiAgentOrchestrator
from ._auth import Principal, require_authenticated_user
from .scope import datasource_scope_id

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

_db: Optional[Database] = None


class DispatchRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=2000)
    subtasks: Optional[List[dict]] = None


def init_orchestration_api(db: Database) -> None:
    global _db
    _db = db


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=503, detail="Orchestration API not initialized")
    return _db


def _memory_for(principal: Principal) -> OrchestrationMemory:
    tenant_id = datasource_scope_id(principal)
    return OrchestrationMemory(db=_require_db(), tenant_id=tenant_id)


@router.get("/tasks")
async def list_orchestration_tasks(
    principal: Principal = Depends(require_authenticated_user),
    page: int = 1,
    page_size: int = 20,
):
    return _memory_for(principal).list_tasks(page=page, page_size=page_size)


@router.get("/tasks/{task_id}")
async def get_orchestration_task(
    task_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    mem = _memory_for(principal)
    detail = mem.get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    task = detail["task"]
    if not principal.is_admin and task.get("tenant_id") != datasource_scope_id(principal):
        raise HTTPException(status_code=403, detail="无权查看该调度任务")
    return detail


@router.post("/dispatch")
async def dispatch_orchestration(
    payload: DispatchRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    tenant_id = datasource_scope_id(principal)
    orch = MultiAgentOrchestrator(db=_require_db(), tenant_id=tenant_id)
    result = await orch.orchestrate(
        session_id=payload.session_id,
        goal=payload.goal,
        subtasks=payload.subtasks,
    )
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "调度失败"))
    return result
