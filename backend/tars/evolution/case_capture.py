"""CaseCapture — record agent task trajectories for Self-Evolving Skills.

Wired into EvolutionManager.ingest_turn() so every completed agent turn
is persisted as an AgentCase.  The CaseDistiller later queries pending
cases and distills patterns into reusable Skills.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .case_models import AgentCase


class CaseCapture:
    """Write agent task trajectories to agent_cases table."""

    def __init__(self, db):
        self._db = db

    # ------------------------------------------------------------------
    # write
    # ------------------------------------------------------------------
    def record_turn(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        query: str,
        *,
        tools_used: Optional[List[str]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        skill_id: Optional[str] = None,
        subagent: Optional[str] = None,
        success: bool = True,
    ) -> Optional[str]:
        """Persist one agent turn as an AgentCase.

        Only persists when the turn includes at least one tool call or
        subagent delegation — pure text replies are skipped to keep the
        case table focused on actionable trajectories.
        """
        tools_used = tools_used or []
        tool_results = tool_results or []

        # Skip pure-conversation turns — only capture tool-using trajectories
        if not tools_used and not subagent:
            return None

        case = AgentCase(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            task_description=query[:500],
            tools_used=tools_used,
            tool_results=tool_results,
            skill_id=skill_id or "",
            subagent=subagent or "",
            success=success,
        )

        try:
            conn = self._db._get_conn()
            conn.execute(
                """
                INSERT INTO agent_cases (
                    case_id, tenant_id, user_id, session_id,
                    task_description, task_intent, tools_used,
                    tool_results, skill_id, subagent,
                    success, feedback_score, distilled, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case.case_id,
                    case.tenant_id,
                    case.user_id,
                    case.session_id,
                    case.task_description,
                    case.task_intent,
                    json.dumps(case.tools_used, ensure_ascii=False),
                    json.dumps(case.tool_results, ensure_ascii=False),
                    case.skill_id,
                    case.subagent,
                    1 if case.success else 0,
                    case.feedback_score,
                    0,  # distilled = False
                    case.created_at,
                ),
            )
            conn.commit()
            return case.case_id
        except Exception as exc:
            print(f"[CaseCapture] record_turn error: {exc}")
            return None

    # ------------------------------------------------------------------
    # query for distillation
    # ------------------------------------------------------------------
    def get_pending_cases(
        self,
        tenant_id: str = "default",
        min_success: bool = True,
        limit: int = 200,
    ) -> List[AgentCase]:
        """Return undistilled cases ordered by recency."""
        success_filter = "AND success = 1" if min_success else ""
        try:
            conn = self._db._get_conn()
            cursor = conn.execute(
                f"""
                SELECT case_id, tenant_id, user_id, session_id,
                       task_description, task_intent, tools_used,
                       tool_results, skill_id, subagent,
                       success, feedback_score, distilled, created_at
                FROM agent_cases
                WHERE tenant_id = ? AND distilled = 0 {success_filter}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            )
            rows = cursor.fetchall()
            return [AgentCase.from_db_row(row) for row in rows]
        except Exception as exc:
            print(f"[CaseCapture] get_pending_cases error: {exc}")
            return []

    def count_pending(self, tenant_id: str = "default") -> int:
        """Count undistilled cases for the tenant."""
        try:
            conn = self._db._get_conn()
            row = conn.execute(
                "SELECT COUNT(*) FROM agent_cases WHERE tenant_id = ? AND distilled = 0",
                (tenant_id,),
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def mark_distilled(self, case_ids: List[str]) -> int:
        """Mark cases as distilled after a skill has been generated from them."""
        if not case_ids:
            return 0
        try:
            conn = self._db._get_conn()
            placeholders = ",".join("?" for _ in case_ids)
            conn.execute(
                f"UPDATE agent_cases SET distilled = 1 WHERE case_id IN ({placeholders})",
                case_ids,
            )
            conn.commit()
            return len(case_ids)
        except Exception as exc:
            print(f"[CaseCapture] mark_distilled error: {exc}")
            return 0

    def record_feedback(self, case_id: str, score: float) -> bool:
        """Update feedback_score for a case (thumbs up/down)."""
        try:
            conn = self._db._get_conn()
            conn.execute(
                "UPDATE agent_cases SET feedback_score = ? WHERE case_id = ?",
                (score, case_id),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def get_recent_cases(
        self, tenant_id: str = "default", limit: int = 20
    ) -> List[AgentCase]:
        """Return most recent cases (for dashboard / debugging)."""
        try:
            conn = self._db._get_conn()
            rows = conn.execute(
                """
                SELECT case_id, tenant_id, user_id, session_id,
                       task_description, task_intent, tools_used,
                       tool_results, skill_id, subagent,
                       success, feedback_score, distilled, created_at
                FROM agent_cases
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
            return [AgentCase.from_db_row(row) for row in rows]
        except Exception:
            return []
