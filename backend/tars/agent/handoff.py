"""Subagent handoff protocol — pending_review before merging results."""
from __future__ import annotations

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

    def __init__(self, preview_limit: int = 500):
        self._handoffs: Dict[str, SubagentHandoff] = {}
        self.preview_limit = preview_limit

    def create_pending(
        self,
        *,
        parent_session_id: str,
        subagent_type: str,
        task_summary: str,
        full_result: str,
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
        return handoff

    def get(self, handoff_id: str) -> Optional[SubagentHandoff]:
        return self._handoffs.get(handoff_id)

    def accept(self, handoff_id: str) -> Optional[SubagentHandoff]:
        handoff = self._handoffs.get(handoff_id)
        if not handoff or handoff.status != "pending_review":
            return None
        handoff.status = "accepted"
        handoff.resolved_at = _now_local()
        return handoff

    def reject(self, handoff_id: str) -> Optional[SubagentHandoff]:
        handoff = self._handoffs.get(handoff_id)
        if not handoff or handoff.status != "pending_review":
            return None
        handoff.status = "rejected"
        handoff.resolved_at = _now_local()
        return handoff
