"""数据报表 API 路由 — /api/report"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ...database import Database
from ...api._auth import require_module, require_authenticated_user, Principal
from ..repository import ReportRepository
from ..service import ReportService
from ..chartspec import ChartSpec, VALID_CHART_TYPES


router = APIRouter(prefix="/api/report", tags=["Report"])

_require = require_module("report")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None


def init_report_api(db: Database) -> None:
    global _db
    _db = db


class ChartCreate(BaseModel):
    datasource_id: str
    table_name: str
    name: str
    chart_type: str
    spec: dict[str, Any]


class ChartExecute(BaseModel):
    datasource_id: str
    table_name: str
    spec: dict[str, Any]


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "report"}


@router.get("/chart-types")
def chart_types() -> dict:
    return {"chart_types": sorted(VALID_CHART_TYPES)}


@router.get("/charts")
def list_charts(
    datasource_id: str,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    repo = ReportRepository(_db)
    charts = repo.list_charts(datasource_id=datasource_id, user_id=principal.user_id)
    return {"charts": [c.__dict__ for c in charts]}


@router.post("/charts")
def create_chart(
    body: ChartCreate,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    repo = ReportRepository(_db)
    chart = repo.create_chart(
        datasource_id=body.datasource_id, name=body.name,
        chart_type=body.chart_type, spec=body.spec,
        user_id=principal.user_id,
    )
    return chart.__dict__


@router.delete("/charts/{chart_id}")
def delete_chart(
    chart_id: str,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    ReportRepository(_db).delete_chart(chart_id, user_id=principal.user_id)
    return {"deleted": chart_id}


@router.post("/charts/execute")
def execute_chart(
    body: ChartExecute,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    try:
        spec = ChartSpec.from_dict(body.spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        data = ReportService(_db).execute_chart(
            datasource_id=body.datasource_id,
            table_name=body.table_name,
            spec=spec,
            tenant_id=principal.tenant_id,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "categories": data.categories,
        "series": [{"name": s.name, "data": s.data} for s in data.series],
        "truncated": data.truncated,
    }


@router.post("/charts/validate-spec")
def validate_chart_spec(
    body: ChartExecute,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    try:
        spec = ChartSpec.from_dict(body.spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        errors = ReportService(_db).validate_spec(
            datasource_id=body.datasource_id,
            table_name=body.table_name,
            spec=spec,
            tenant_id=principal.tenant_id,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"valid": len(errors) == 0, "errors": errors}
