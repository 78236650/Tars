"""Plan approval gate — wait for user review with timeout/reminder."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from ..config.plan_gate import PlanGateConfig, plan_gate_config
from ..database.plan_store import PlanStore
from .models import PlanStatus, TaskPlan, auto_approve_eligible


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class PlanGateService:
    def __init__(
        self,
        plan_store: PlanStore,
        config: Optional[PlanGateConfig] = None,
        connection_manager=None,
    ):
        self.plan_store = plan_store
        self.config = config or plan_gate_config
        self.connection_manager = connection_manager
        self._pending: Dict[str, asyncio.Future] = {}
        self._timers: Dict[str, asyncio.Task] = {}

    def _session_has_ws(self, session_id: str) -> bool:
        if not self.connection_manager:
            return False
        return session_id in getattr(self.connection_manager, "session_connections", {})

    async def submit_for_review(self, plan: TaskPlan, channel) -> bool:
        """Return True if approved (or auto-approved), False if rejected/cancelled."""
        if not self.config.enabled:
            self.plan_store.update_status(plan.id, PlanStatus.APPROVED)
            return True

        if auto_approve_eligible(plan, self.config):
            self.plan_store.update_status(plan.id, PlanStatus.APPROVED)
            return True

        if self.config.fallback_auto_approve and not self._session_has_ws(plan.session_id):
            self.plan_store.update_status(plan.id, PlanStatus.APPROVED)
            return True

        self.plan_store.update_status(plan.id, PlanStatus.DRAFT)
        await channel.send(plan.session_id, {
            "type": "plan_review_request",
            "session_id": plan.session_id,
            "plan_id": plan.id,
            "goal": plan.goal,
            "steps": [s.to_dict() for s in plan.steps],
            "estimated_duration_sec": plan.estimated_duration_sec or len(plan.steps) * 30,
            "timestamp": _now_iso(),
        })

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[plan.id] = fut
        self._timers[plan.id] = asyncio.create_task(
            self._watch_review(plan.id, plan.session_id, channel)
        )

        try:
            result = await asyncio.wait_for(fut, timeout=self.config.review_timeout_sec)
            return bool(result.get("approved"))
        except asyncio.TimeoutError:
            self.plan_store.update_status(plan.id, PlanStatus.CANCELLED)
            await channel.send(plan.session_id, {
                "type": "plan_review_cancelled",
                "session_id": plan.session_id,
                "plan_id": plan.id,
                "reason": "timeout",
                "timestamp": _now_iso(),
            })
            return False
        finally:
            self._pending.pop(plan.id, None)
            timer = self._timers.pop(plan.id, None)
            if timer and not timer.done():
                timer.cancel()

    async def _watch_review(self, plan_id: str, session_id: str, channel) -> None:
        try:
            await asyncio.sleep(self.config.reminder_at_sec)
            if plan_id not in self._pending:
                return
            await channel.send(session_id, {
                "type": "plan_review_reminder",
                "session_id": session_id,
                "plan_id": plan_id,
                "message": "计划仍在等待审批",
                "timestamp": _now_iso(),
            })
        except asyncio.CancelledError:
            pass

    def approve(self, plan_id: str, steps: Optional[list] = None) -> bool:
        plan = self.plan_store.get(plan_id)
        if not plan:
            return False
        if steps is not None:
            self.plan_store.update_steps(plan_id, steps)
        self.plan_store.update_status(plan_id, PlanStatus.APPROVED)
        self._resolve(plan_id, {"approved": True})
        return True

    def reject(self, plan_id: str) -> bool:
        if not self.plan_store.get(plan_id):
            return False
        self.plan_store.update_status(plan_id, PlanStatus.REJECTED)
        self._resolve(plan_id, {"approved": False})
        return True

    def cancel(self, plan_id: str) -> bool:
        if not self.plan_store.get(plan_id):
            return False
        self.plan_store.update_status(plan_id, PlanStatus.CANCELLED)
        self._resolve(plan_id, {"approved": False})
        return True

    def _resolve(self, plan_id: str, result: Dict[str, Any]) -> None:
        fut = self._pending.get(plan_id)
        if fut and not fut.done():
            fut.set_result(result)


_plan_gate_singleton: Optional[PlanGateService] = None


def init_plan_gate(plan_store: PlanStore, connection_manager=None, config=None) -> PlanGateService:
    global _plan_gate_singleton
    _plan_gate_singleton = PlanGateService(plan_store, config=config, connection_manager=connection_manager)
    return _plan_gate_singleton


def get_plan_gate() -> Optional[PlanGateService]:
    return _plan_gate_singleton
