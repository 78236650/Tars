"""Human-in-the-loop approval for high-risk tool execution."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..database.base import ApprovalRequest


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class ApprovalService:
    def __init__(
        self,
        db,
        connection_manager=None,
        *,
        channel_router=None,
        timeout_seconds: int = 300,
        grace_seconds: int = 120,
    ):
        from ..channels.outbound import OutboundDeliverer

        self.db = db
        self.connection_manager = connection_manager
        self.outbound = OutboundDeliverer(
            channel_router=channel_router,
            connection_manager=connection_manager,
        )
        self.timeout_seconds = timeout_seconds
        # v5.0.5/A2: 超时后的宽限窗口 —— 审批超时返回拒绝执行,但在宽限期内
        # 迟到的人工审批仍会被记录(便于审计与重放),且会发提醒事件。
        self.grace_seconds = grace_seconds
        self._waiters: Dict[str, asyncio.Event] = {}
        self._outcomes: Dict[str, str] = {}

    async def request_approval(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """向后兼容的布尔接口:仅当审批通过返回 True。"""
        outcome = await self.request_approval_detailed(tool_name, arguments, context)
        return outcome == "approved"

    async def request_approval_detailed(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """发起审批并返回精确结果字符串(v5.0.5/A2)。

        返回 "approved" | "denied" | "timeout",供调用方区分超时与拒绝。
        """
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "default")
        user_id = ctx.get("user_id", "default")
        session_id = ctx.get("session_id", "default")
        args_json = json.dumps(arguments or {}, ensure_ascii=False, default=str)

        request = self.db.create_approval_request(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=args_json,
        )

        await self._emit(
            session_id,
            {
                "type": "approval_required",
                "approval_id": request.id,
                "session_id": session_id,
                "tool_name": tool_name,
                "arguments_summary": self._summarize_arguments(arguments),
                "timeout_seconds": self.timeout_seconds,
                "timestamp": _now_local().isoformat(),
            },
        )

        event = asyncio.Event()
        self._waiters[request.id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            await self._resolve(request.id, "timeout", resolved_by="system")
            return "timeout"
        finally:
            self._waiters.pop(request.id, None)

        return self._outcomes.pop(request.id, "denied")

    async def approve(self, approval_id: str, resolved_by: str) -> Optional[ApprovalRequest]:
        return await self._resolve_external(approval_id, "approved", resolved_by)

    async def deny(self, approval_id: str, resolved_by: str) -> Optional[ApprovalRequest]:
        return await self._resolve_external(approval_id, "denied", resolved_by)

    async def _resolve_external(
        self, approval_id: str, status: str, resolved_by: str
    ) -> Optional[ApprovalRequest]:
        """处理来自 API 的 approve/deny(v5.0.5/A2)。

        若请求仍 pending:正常解析并唤醒等待者。
        若请求已 timeout 但在宽限窗口内:记录为迟到决策(status 前缀 late_),
        不再唤醒(等待者早已超时返回),仅用于审计与可能的重放。
        """
        existing = self.db.get_approval_request(approval_id)
        if not existing:
            return None

        if existing.status == "pending":
            updated = self.db.update_approval_request(
                approval_id, status=status, resolved_by=resolved_by
            )
            if not updated:
                return None
            await self._resolve(approval_id, status, resolved_by=resolved_by, request=updated)
            return updated

        if existing.status == "timeout" and self._within_grace(existing):
            late_status = f"late_{status}"
            updated = self.db.update_approval_request(
                approval_id,
                status=late_status,
                resolved_by=resolved_by,
                expected_status="timeout",
            )
            if updated:
                await self._emit(
                    updated.session_id,
                    {
                        "type": "approval_resolved_late",
                        "approval_id": approval_id,
                        "session_id": updated.session_id,
                        "tool_name": updated.tool_name,
                        "status": late_status,
                        "resolved_by": resolved_by,
                        "note": "审批已超时,此为宽限窗口内的迟到决策,仅记录不重新放行",
                        "timestamp": _now_local().isoformat(),
                    },
                )
            return updated

        # 已是终态(approved/denied/late_*)或超出宽限窗口:幂等返回当前状态
        return existing

    def _within_grace(self, request: ApprovalRequest) -> bool:
        """请求创建时间是否仍在 timeout + grace 窗口内。"""
        try:
            created = request.created_at
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone(timedelta(hours=8)))
            deadline = created + timedelta(
                seconds=self.timeout_seconds + self.grace_seconds
            )
            return _now_local() <= deadline
        except Exception:
            return False

    async def _resolve(
        self,
        approval_id: str,
        outcome: str,
        *,
        resolved_by: str = "",
        request: Optional[ApprovalRequest] = None,
    ) -> None:
        if outcome == "timeout":
            self.db.update_approval_request(approval_id, status="timeout", resolved_by=resolved_by)
        self._outcomes[approval_id] = outcome
        waiter = self._waiters.get(approval_id)
        if waiter:
            waiter.set()

        req = request or self.db.get_approval_request(approval_id)
        if req:
            await self._emit(
                req.session_id,
                {
                    "type": "approval_resolved",
                    "approval_id": approval_id,
                    "session_id": req.session_id,
                    "tool_name": req.tool_name,
                    "status": outcome,
                    "resolved_by": resolved_by,
                    "timestamp": _now_local().isoformat(),
                },
            )

    async def _emit(self, session_id: str, event: dict) -> None:
        if not session_id:
            return
        try:
            await self.outbound.send_personal(session_id, event)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("approval emit failed", exc_info=exc)

    @staticmethod
    def _summarize_arguments(arguments: Optional[Dict[str, Any]]) -> str:
        if not arguments:
            return ""
        try:
            from .sanitizer import sanitizer

            text = json.dumps(arguments, ensure_ascii=False, default=str)
            return sanitizer.sanitize(text)[:500]
        except Exception:
            return str(arguments)[:500]


approval_service: Optional[ApprovalService] = None


def init_approval_service(
    db,
    connection_manager=None,
    *,
    channel_router=None,
    timeout_seconds: Optional[int] = None,
    grace_seconds: Optional[int] = None,
) -> ApprovalService:
    global approval_service
    from .execution_policy import execution_policy

    timeout = timeout_seconds if timeout_seconds is not None else execution_policy.timeout_seconds
    import os
    grace = grace_seconds if grace_seconds is not None else int(os.getenv("TARS_APPROVAL_GRACE", "120"))
    approval_service = ApprovalService(
        db,
        connection_manager,
        channel_router=channel_router,
        timeout_seconds=timeout,
        grace_seconds=grace,
    )
    return approval_service
