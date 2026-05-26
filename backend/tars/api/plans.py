"""Plan approval REST API — v4.3.2"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..database import Database
from ..database.plan_store import PlanStore, get_plan_store, init_plan_store
from ..database.audit_store import init_verification_audit_store, get_verification_audit_store
from ..orchestration.plan_gate import PlanGateService, get_plan_gate, init_plan_gate
from ..orchestration.plan_resume import get_plan_resume, init_plan_resume
from ._auth import Principal, require_authenticated_user

router = APIRouter(prefix="/api/plans", tags=["plans"])

_db: Optional[Database] = None
_plan_store: Optional[PlanStore] = None


class PlanStepsUpdate(BaseModel):
    steps: Optional[List[Dict[str, Any]]] = None


def init_plans_api(
    db: Database,
    connection_manager=None,
    task_executor=None,
    skill_registry=None,
    channel_router=None,
) -> None:
    global _db, _plan_store
    _db = db
    _plan_store = init_plan_store(db)
    init_verification_audit_store(db)
    init_plan_gate(_plan_store, connection_manager=connection_manager)
    if task_executor is not None:
        init_plan_resume(
            task_executor,
            skill_registry=skill_registry,
            connection_manager=connection_manager,
            channel_router=channel_router,
        )


def _store() -> PlanStore:
    if _plan_store is not None:
        return _plan_store
    return get_plan_store()


def _gate() -> PlanGateService:
    gate = get_plan_gate()
    if gate is None:
        raise HTTPException(status_code=503, detail="Plan gate not initialized")
    return gate


@router.get("")
async def list_plans(
    principal: Principal = Depends(require_authenticated_user),
    limit: int = 50,
):
    tenant_id = principal.tenant_id or "default"
    plans = _store().list_by_tenant(tenant_id, limit=limit)
    return {"plans": [p.to_dict() for p in plans]}


@router.get("/{plan_id}")
async def get_plan(
    plan_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    detail = _store().get_detail(plan_id)
    if not detail:
        raise HTTPException(status_code=404, detail="计划不存在")
    if not principal.is_admin and detail.get("tenant_id") != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权查看该计划")
    return detail


@router.post("/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    body: PlanStepsUpdate = PlanStepsUpdate(),
    principal: Principal = Depends(require_authenticated_user),
):
    plan = _store().get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if not principal.is_admin and plan.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权审批该计划")
    ok = _gate().approve(plan_id, steps=body.steps)
    if not ok:
        raise HTTPException(status_code=409, detail="审批失败")
    return {"success": True, "plan_id": plan_id, "status": "approved"}


@router.post("/{plan_id}/reject")
async def reject_plan(
    plan_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    plan = _store().get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if not principal.is_admin and plan.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权拒绝该计划")
    ok = _gate().reject(plan_id)
    if not ok:
        raise HTTPException(status_code=409, detail="拒绝失败")
    return {"success": True, "plan_id": plan_id, "status": "rejected"}


@router.post("/{plan_id}/retry")
async def retry_plan(
    plan_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    plan = _store().get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if not principal.is_admin and plan.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权重试该计划")

    resume_svc = get_plan_resume()
    if resume_svc is None:
        raise HTTPException(status_code=503, detail="Plan resume service not initialized")

    try:
        resume_from = await resume_svc.schedule_resume(plan_id, _store())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "success": True,
        "plan_id": plan_id,
        "status": "executing",
        "resume_from_step": resume_from,
    }


@router.get("/{plan_id}/verification")
async def get_plan_verification(
    plan_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    plan = _store().get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    if not principal.is_admin and plan.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="无权查看该计划")
    items = get_verification_audit_store().list_by_plan(plan_id)
    return {"plan_id": plan_id, "items": items}
