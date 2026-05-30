"""Subagent handoff protocol — pending_review before merging results."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional


HandoffStatus = Literal["running", "pending_review", "accepted", "rejected"]


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


@dataclass
class SubagentHandoff:
    id: str
    status: HandoffStatus
    subagent_type: str
    task_summary: str
    result_preview: str
    parent_session_id: str
    full_result: str = ""
    created_at: datetime = field(default_factory=_now_local)
    resolved_at: Optional[datetime] = None

    def to_ws_payload(self) -> dict:
        return {
            "handoff_id": self.id,
            "status": self.status,
            "subagent_type": self.subagent_type,
            "task_summary": self.task_summary,
            "result_preview": self.result_preview,
            "parent_session_id": self.parent_session_id,
        }


class HandoffManager:
    """In-memory pending subagent handoffs keyed by handoff id."""

    def __init__(self, preview_limit: int = 500, db=None):
        self._handoffs: Dict[str, SubagentHandoff] = {}
        self._db = db
        self.preview_limit = preview_limit

    def create_pending(
        self,
        *,
        parent_session_id: str,
        subagent_type: str,
        task_summary: str,
        full_result: str,
        tenant_id: str = "default",
        user_id: str = "default",
    ) -> SubagentHandoff:
        preview = full_result
        if len(preview) > self.preview_limit:
            preview = preview[: self.preview_limit] + "…"
        handoff = SubagentHandoff(
            id=str(uuid.uuid4()),
            status="pending_review",
            subagent_type=subagent_type,
            task_summary=task_summary,
            result_preview=preview,
            parent_session_id=parent_session_id,
            full_result=full_result,
        )
        self._handoffs[handoff.id] = handoff
        if self._db:
            self._db.execute(
                "INSERT INTO approval_requests (id,tenant_id,user_id,session_id,tool_name,arguments,status,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    handoff.id,
                    tenant_id,
                    user_id,
                    parent_session_id,
                    "subagent_handoff",
                    json.dumps(handoff.to_ws_payload(), ensure_ascii=False),
                    "pending",
                    _now_local().isoformat(),
                ),
            )
        return handoff

    def get(self, handoff_id: str) -> Optional[SubagentHandoff]:
        return self._handoffs.get(handoff_id)

    def accept(self, handoff_id: str, resolved_by: str = "") -> Optional[SubagentHandoff]:
        handoff = self._handoffs.get(handoff_id)
        if not handoff or handoff.status != "pending_review":
            return None
        handoff.status = "accepted"
        handoff.resolved_at = _now_local()
        if self._db:
            self._db.execute(
                "UPDATE approval_requests SET status=?, resolved_at=?, resolved_by=? WHERE id=?",
                ("accepted", _now_local().isoformat(), resolved_by, handoff_id),
            )
        return handoff

    def reject(self, handoff_id: str, resolved_by: str = "") -> Optional[SubagentHandoff]:
        handoff = self._handoffs.get(handoff_id)
        if not handoff or handoff.status != "pending_review":
            return None
        handoff.status = "rejected"
        handoff.resolved_at = _now_local()
        if self._db:
            self._db.execute(
                "UPDATE approval_requests SET status=?, resolved_at=?, resolved_by=? WHERE id=?",
                ("rejected", _now_local().isoformat(), resolved_by, handoff_id),
            )
        return handoff
