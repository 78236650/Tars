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
    def __init__(self, db, connection_manager=None, *, timeout_seconds: int = 300):
        self.db = db
        self.connection_manager = connection_manager
        self.timeout_seconds = timeout_seconds
        self._waiters: Dict[str, asyncio.Event] = {}
        self._outcomes: Dict[str, str] = {}

    async def request_approval(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
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
                "timestamp": _now_local().isoformat(),
            },
        )

        event = asyncio.Event()
        self._waiters[request.id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            await self._resolve(request.id, "timeout", resolved_by="system")
            return False
        finally:
            self._waiters.pop(request.id, None)

        outcome = self._outcomes.pop(request.id, "denied")
        return outcome == "approved"

    async def approve(self, approval_id: str, resolved_by: str) -> Optional[ApprovalRequest]:
        updated = self.db.update_approval_request(
            approval_id,
            status="approved",
            resolved_by=resolved_by,
        )
        if not updated:
            return None
        await self._resolve(approval_id, "approved", resolved_by=resolved_by, request=updated)
        return updated

    async def deny(self, approval_id: str, resolved_by: str) -> Optional[ApprovalRequest]:
        updated = self.db.update_approval_request(
            approval_id,
            status="denied",
            resolved_by=resolved_by,
        )
        if not updated:
            return None
        await self._resolve(approval_id, "denied", resolved_by=resolved_by, request=updated)
        return updated

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
        if not self.connection_manager or not session_id:
            return
        try:
            await self.connection_manager.send_personal_message(session_id, event)
        except Exception:
            pass

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


def init_approval_service(db, connection_manager=None, *, timeout_seconds: Optional[int] = None) -> ApprovalService:
    global approval_service
    from .execution_policy import execution_policy

    timeout = timeout_seconds if timeout_seconds is not None else execution_policy.timeout_seconds
    approval_service = ApprovalService(db, connection_manager, timeout_seconds=timeout)
    return approval_service
