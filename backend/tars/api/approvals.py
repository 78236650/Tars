"""Tool approval REST API — v4.3.0 Phase 3."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..database import Database
from ..security.approval_service import approval_service as _approval_service
from ..security.approval_service import init_approval_service
from ._auth import Principal, require_authenticated_user

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

_db: Optional[Database] = None


def init_approval_api(db: Database, connection_manager=None, channel_router=None) -> None:
    global _db
    _db = db
    init_approval_service(db, connection_manager, channel_router=channel_router)


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


def _require_service():
    if _approval_service is None:
        raise HTTPException(status_code=503, detail="Approval service not initialized")
    return _approval_service


def _authorize_request(principal: Principal, request) -> None:
    if principal.is_admin:
        return
    if request.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="无权审批该请求")


@router.get("/{approval_id}")
async def get_approval_status(
    approval_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    """查询单个审批请求状态(v5.0.5/A2)。"""
    service = _require_service()
    request = service.db.get_approval_request(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    _authorize_request(principal, request)
    return {
        "success": True,
        "approval_id": approval_id,
        "status": request.status,
        "tool_name": request.tool_name,
        "session_id": request.session_id,
        "created_at": str(request.created_at),
        "resolved_at": str(request.resolved_at) if request.resolved_at else None,
        "resolved_by": request.resolved_by,
    }


@router.get("")
async def list_pending_approvals(
    principal: Principal = Depends(require_authenticated_user),
):
    """列出待处理审批请求(v5.0.5/A2)。

    进程重启后可借此恢复待审批列表 —— 状态本就持久化在 DB,不依赖内存等待器。
    非管理员仅看到自己的请求。
    """
    service = _require_service()
    pending = service.db.list_pending_approval_requests()
    items = [
        {
            "approval_id": r.id,
            "status": r.status,
            "tool_name": r.tool_name,
            "session_id": r.session_id,
            "user_id": r.user_id,
            "created_at": str(r.created_at),
        }
        for r in pending
        if principal.is_admin or r.user_id == principal.user_id
    ]
    return {"success": True, "count": len(items), "pending": items}


@router.post("/{approval_id}/approve")
async def approve_tool_execution(
    approval_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    _require_db()
    service = _require_service()
    request = service.db.get_approval_request(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    # v5.0.5/A2: pending 正常处理;timeout 交由 service 判断宽限窗口;其余终态拒绝。
    if request.status not in ("pending", "timeout"):
        raise HTTPException(status_code=409, detail=f"审批请求已处理: {request.status}")
    _authorize_request(principal, request)
    updated = await service.approve(approval_id, resolved_by=principal.user_id)
    if not updated:
        raise HTTPException(status_code=409, detail="审批失败")
    return {"success": True, "approval_id": approval_id, "status": updated.status}


@router.post("/{approval_id}/deny")
async def deny_tool_execution(
    approval_id: str,
    principal: Principal = Depends(require_authenticated_user),
):
    _require_db()
    service = _require_service()
    request = service.db.get_approval_request(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    if request.status not in ("pending", "timeout"):
        raise HTTPException(status_code=409, detail=f"审批请求已处理: {request.status}")
    _authorize_request(principal, request)
    updated = await service.deny(approval_id, resolved_by=principal.user_id)
    if not updated:
        raise HTTPException(status_code=409, detail="拒绝失败")
    return {"success": True, "approval_id": approval_id, "status": updated.status}
