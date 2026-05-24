"""Skill description optimization suggestions from usage stats."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class SkillOptimizer:
    def __init__(self, db, min_calls: int = 10, low_success_rate: float = 0.4):
        self.db = db
        self.min_calls = min_calls
        self.low_success_rate = low_success_rate

    def suggest_patches(self) -> List[Dict[str, Any]]:
        conn = self.db._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT skill_id, total_calls,
                       COALESCE(success_count, 0), COALESCE(fail_count, 0)
                FROM skill_usage
                WHERE total_calls >= ?
                """,
                (self.min_calls,),
            ).fetchall()
        except Exception:
            return []

        suggestions: List[Dict[str, Any]] = []
        for skill_id, total, success, fail in rows:
            denom = success + fail
            if denom <= 0:
                continue
            rate = success / denom
            if rate < self.low_success_rate:
                suggestions.append(
                    {
                        "skill_id": skill_id,
                        "success_rate": round(rate, 3),
                        "total_calls": total,
                        "suggestion": f"Clarify SKILL.md description for {skill_id} (success rate {rate:.0%})",
                    }
                )
        return suggestions
