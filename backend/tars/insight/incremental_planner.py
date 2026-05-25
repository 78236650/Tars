"""Incremental table collection planning for InsightForge Profile."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .config import InsightBudget
from .schema_fingerprint import fingerprint_schema


@dataclass
class CollectPlan:
    actions: Dict[str, str] = field(default_factory=dict)
    reused_count: int = 0
    collected_count: int = 0
    dropped_count: int = 0
    resampled_count: int = 0
    profile_run_type: str = "full"


class IncrementalPlanner:
    def __init__(self, budget: InsightBudget):
        self.budget = budget

    def plan(
        self,
        schema: Dict[str, Any],
        previous_snapshot: Optional[Dict[str, Any]],
        *,
        force: bool = False,
        previous_completed_at: Optional[str] = None,
    ) -> CollectPlan:
        tables = schema.get("tables") or {}
        table_names = sorted(tables.keys())
        plan = CollectPlan()

        if force or not self.budget.enable_incremental or not previous_snapshot:
            plan.actions = {t: "collect" for t in table_names}
            plan.collected_count = len(table_names)
            plan.profile_run_type = "full"
            return plan

        if self._ttl_expired(previous_completed_at):
            plan.actions = {t: "collect" for t in table_names}
            plan.collected_count = len(table_names)
            plan.profile_run_type = "full"
            return plan

        current_fp = fingerprint_schema(schema)
        prev_fp = previous_snapshot.get("fingerprints") or {}
        prev_tables = previous_snapshot.get("tables") or {}

        for t in table_names:
            if t not in prev_tables:
                plan.actions[t] = "collect"
                plan.collected_count += 1
            elif current_fp.get(t) == prev_fp.get(t):
                plan.actions[t] = "reuse"
                plan.reused_count += 1
            else:
                plan.actions[t] = "collect"
                plan.collected_count += 1

        for t in prev_tables:
            if t not in tables:
                plan.dropped_count += 1

        plan.profile_run_type = "incremental" if plan.reused_count > 0 else "full"
        return plan

    def _ttl_expired(self, previous_completed_at: Optional[str]) -> bool:
        if not previous_completed_at:
            return False
        try:
            ts = previous_completed_at.replace("Z", "+00:00")
            completed = datetime.fromisoformat(ts)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - completed.astimezone(timezone.utc)
            return age > timedelta(hours=self.budget.incremental_ttl_hours)
        except (ValueError, TypeError):
            return False
