"""Skill description optimization suggestions from usage stats."""
from __future__ import annotations

from typing import Any, Dict, List

from ..database.skill_routing_store import get_skill_routing_store


class SkillOptimizer:
    def __init__(
        self,
        db,
        min_calls: int = 10,
        low_success_rate: float = 0.4,
        min_recommendations: int = 10,
        low_adoption_rate: float = 0.4,
    ):
        self.db = db
        self.min_calls = min_calls
        self.low_success_rate = low_success_rate
        self.min_recommendations = min_recommendations
        self.low_adoption_rate = low_adoption_rate

    def suggest_patches(self) -> List[Dict[str, Any]]:
        suggestions = self._suggest_from_usage()
        seen = {s["skill_id"] for s in suggestions}
        for item in self.suggest_trigger_patches():
            if item["skill_id"] not in seen:
                suggestions.append(item)
        return suggestions

    def _suggest_from_usage(self) -> List[Dict[str, Any]]:
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
                        "kind": "usage",
                        "success_rate": round(rate, 3),
                        "total_calls": total,
                        "suggestion": f"Clarify SKILL.md description for {skill_id} (success rate {rate:.0%})",
                    }
                )
        return suggestions

    def suggest_trigger_patches(self) -> List[Dict[str, Any]]:
        store = get_skill_routing_store()
        if store is None:
            return []
        suggestions: List[Dict[str, Any]] = []
        for row in store.adoption_stats(min_recommendations=self.min_recommendations):
            rate = row["adoption_rate"]
            if rate >= self.low_adoption_rate:
                continue
            suggestions.append(
                {
                    "skill_id": row["skill_id"],
                    "kind": "routing",
                    "adoption_rate": rate,
                    "recommendations": row["recommendations"],
                    "adoptions": row["adoptions"],
                    "suggestion": (
                        f"Tighten triggers/skip_when for {row['skill_id']} "
                        f"(router adoption {rate:.0%} over {row['recommendations']} recommendations)"
                    ),
                }
            )
        return suggestions
