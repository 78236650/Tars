"""Agent Case data models for Self-Evolving Skills.
Each AgentCase records a completed agent task trajectory.
CaseSummary is a lightweight struct for clustering before distillation.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


@dataclass
class AgentCase:
    """A single agent task execution record."""

    tenant_id: str
    user_id: str
    task_description: str
    tools_used: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    case_id: str = ""
    session_id: str = ""
    task_intent: str = ""
    skill_id: str = ""
    subagent: str = ""
    feedback_score: float = 0.0
    distilled: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.case_id:
            self.case_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = _now_iso()

    def to_db_row(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "task_description": self.task_description,
            "task_intent": self.task_intent,
            "tools_used": json.dumps(self.tools_used, ensure_ascii=False),
            "tool_results": json.dumps(self.tool_results, ensure_ascii=False),
            "skill_id": self.skill_id,
            "subagent": self.subagent,
            "success": 1 if self.success else 0,
            "feedback_score": self.feedback_score,
            "distilled": 1 if self.distilled else 0,
            "created_at": self.created_at,
        }

    @classmethod
    def from_db_row(cls, row: tuple) -> AgentCase:
        """Parse a SQLite row into AgentCase."""
        (
            case_id,
            tenant_id,
            user_id,
            session_id,
            task_description,
            task_intent,
            tools_used_raw,
            tool_results_raw,
            skill_id,
            subagent,
            success,
            feedback_score,
            distilled,
            created_at,
        ) = row
        try:
            tools_used = json.loads(tools_used_raw or "[]")
        except (json.JSONDecodeError, TypeError):
            tools_used = []
        try:
            tool_results = json.loads(tool_results_raw or "[]")
        except (json.JSONDecodeError, TypeError):
            tool_results = []
        return cls(
            case_id=case_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id or "",
            task_description=task_description,
            task_intent=task_intent or "",
            tools_used=tools_used,
            tool_results=tool_results,
            skill_id=skill_id or "",
            subagent=subagent or "",
            success=bool(success),
            feedback_score=float(feedback_score or 0.0),
            distilled=bool(distilled),
            created_at=created_at or "",
        )

    def summary_for_distillation(self) -> str:
        """One-paragraph summary for the distillation LLM prompt."""
        tools_str = ", ".join(self.tools_used) if self.tools_used else "none"
        outcome = "success" if self.success else "failure"
        lines = [
            f"Task: {self.task_description}",
            f"Tools used: {tools_str}",
            f"Outcome: {outcome}",
        ]
        if self.tool_results:
            brief_results = []
            for tr in self.tool_results[:5]:
                name = tr.get("name", "?")
                ok = tr.get("ok", tr.get("success", True))
                brief_results.append(f"{name}({'ok' if ok else 'fail'})")
            lines.append(f"Tool results: {', '.join(brief_results)}")
        if self.subagent:
            lines.append(f"Subagent: {self.subagent}")
        return "\n".join(lines)


@dataclass
class CaseSummary:
    """Lightweight summary for grouping similar cases before distillation."""

    task_description: str
    case_count: int
    success_count: int
    common_tools: List[str]
    sample_case_ids: List[str] = field(default_factory=list)
    representative_tasks: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.case_count == 0:
            return 0.0
        return self.success_count / self.case_count
