"""Subagent handoff accept/reject REST API — v4.3.0 Phase 3."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ._auth import Principal, require_authenticated_user

router = APIRouter(prefix="/api/handoffs", tags=["handoffs"])

_agent: Any = None
_connection_manager: Any = None


def init_handoff_api(agent, connection_manager=None) -> None:
    global _agent, _connection_manager
    _agent = agent
    _connection_manager = connection_manager


def _require_agent():
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return _agent


@router.post("/{handoff_id}/accept")
async def accept_handoff(
    handoff_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    agent = _require_agent()
    handoff = agent.handoff_manager.get(handoff_id)
    if not handoff:
        raise HTTPException(status_code=404, detail="Handoff 不存在")
    ok = await agent.handle_subagent_handoff_action(
        handoff_id,
        "accept",
        connection_manager=_connection_manager,
        tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Handoff 无法接受")
    return {"success": True, "handoff_id": handoff_id, "status": "accepted"}


@router.post("/{handoff_id}/reject")
async def reject_handoff(
    handoff_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    agent = _require_agent()
    handoff = agent.handoff_manager.get(handoff_id)
    if not handoff:
        raise HTTPException(status_code=404, detail="Handoff 不存在")
    ok = await agent.handle_subagent_handoff_action(
        handoff_id,
        "reject",
        connection_manager=_connection_manager,
        tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Handoff 无法拒绝")
    return {"success": True, "handoff_id": handoff_id, "status": "rejected"}
