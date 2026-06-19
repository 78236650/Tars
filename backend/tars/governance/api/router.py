"""数据治理 API 路由 — /api/governance"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ...database import Database
from ...api._auth import require_module, require_authenticated_user, Principal
from ..repository import GovernanceRepository
from ..service import GovernanceService


router = APIRouter(prefix="/api/governance", tags=["Governance"])

_require = require_module("governance")
router.dependencies = [Depends(_require)]

_db: Optional[Database] = None


def init_governance_api(db: Database) -> None:
    global _db
    _db = db


class RuleCreate(BaseModel):
    datasource_id: str
    table_name: str
    kind: str
    name: str
    params: dict[str, Any] = {}
    engine: str = "builtin"


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "governance"}


@router.get("/rule-kinds")
def rule_kinds() -> dict:
    from ..rules import available_rules
    return {"kinds": available_rules()}


@router.get("/rules")
def list_rules(
    datasource_id: str,
    table_name: Optional[str] = None,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    repo = GovernanceRepository(_db)
    rules = repo.list_rules(
        datasource_id=datasource_id, table_name=table_name,
        user_id=principal.user_id,
    )
    return {"rules": [r.__dict__ for r in rules]}


@router.post("/rules")
def create_rule(
    body: RuleCreate,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    repo = GovernanceRepository(_db)
    rule = repo.create_rule(
        datasource_id=body.datasource_id, kind=body.kind,
        name=body.name, table_name=body.table_name,
        params=body.params, engine=body.engine,
        user_id=principal.user_id,
    )
    return rule.__dict__


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    GovernanceRepository(_db).delete_rule(rule_id, user_id=principal.user_id)
    return {"deleted": rule_id}


@router.post("/validate")
def validate(
    datasource_id: str,
    table_name: str,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    try:
        run = GovernanceService(_db).run_validation(
            datasource_id=datasource_id, table_name=table_name,
            user_id=principal.user_id, tenant_id=principal.tenant_id,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return run.__dict__
