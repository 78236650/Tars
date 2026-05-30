"""船舶进出港计划 REST API — v4.5.0."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import Database
from ..orchestration.multi_agent_orchestrator import MultiAgentOrchestrator
from ..vessel_plan.service import VesselPlanService
from ._auth import Principal, require_authenticated_user
from .scope import datasource_scope_id

router = APIRouter(prefix="/api/vessel-plans", tags=["vessel-plans"])

_db: Optional[Database] = None


def init_vessel_plan_api(db: Database) -> None:
    global _db
    _db = db


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=503, detail="Vessel plan API not initialized")
    return _db


def _service_for(principal: Principal) -> VesselPlanService:
    return VesselPlanService(_require_db(), tenant_id=datasource_scope_id(principal))


class OptimizeRequest(BaseModel):
    horizon_hours: int = Field(default=48, ge=1, le=168)


class PatchAssignmentRequest(BaseModel):
    berth_id: Optional[str] = None
    etb: Optional[str] = None
    etd: Optional[str] = None
    locked: Optional[bool] = None


class AdoptRequest(BaseModel):
    voyage_ids: List[str] = Field(min_length=1)
    session_id: str = Field(min_length=1, max_length=128)


@router.get("/demo/status")
async def demo_status(principal: Principal = Depends(require_authenticated_user)):
    return _service_for(principal).demo_status()


@router.post("/demo/reset")
async def demo_reset(principal: Principal = Depends(require_authenticated_user)):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可重置演示数据")
    return _service_for(principal).reset_demo()


@router.get("/berths")
async def list_berths(principal: Principal = Depends(require_authenticated_user)):
    svc = _service_for(principal)
    svc.ensure_seeded()
    berths = svc.repo.list_berths()
    return [VesselPlanService._berth_dict(b) for b in berths]


@router.get("/horizon")
async def get_horizon(
    hours: int = 48,
    principal: Principal = Depends(require_authenticated_user),
):
    return _service_for(principal).get_horizon(horizon_hours=hours)


@router.post("/optimize")
async def optimize_plan(
    body: OptimizeRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    return _service_for(principal).optimize(horizon_hours=body.horizon_hours)


@router.post("/recompute")
async def recompute_plan(
    body: OptimizeRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    return _service_for(principal).recompute(horizon_hours=body.horizon_hours)


@router.patch("/assignments/{voyage_id}")
async def patch_assignment(
    voyage_id: str,
    body: PatchAssignmentRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    try:
        return _service_for(principal).patch_assignment(
            voyage_id,
            berth_id=body.berth_id,
            etb=body.etb,
            etd=body.etd,
            locked=body.locked,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/voyages/{voyage_id}")
async def get_voyage_detail(
    voyage_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    try:
        return _service_for(principal).get_voyage_detail(voyage_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/adopt")
async def adopt_plans(
    body: AdoptRequest,
    principal: Principal = Depends(require_authenticated_user),
):
    tenant_id = datasource_scope_id(principal)
    svc = _service_for(principal)
    orch = MultiAgentOrchestrator(db=_require_db(), tenant_id=tenant_id)
    return await svc.adopt(body.voyage_ids, body.session_id, orch)
