"""Background plan resume — wires POST /api/plans/{id}/retry to TaskExecutor.resume()."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from ..channels.outbound import OutboundDeliverer
from ..database.audit_store import get_verification_audit_store
from ..database.plan_store import PlanStore, get_plan_store
from ..orchestration.models import PlanStatus

logger = logging.getLogger(__name__)


class SessionOutboundChannel:
    """Minimal channel adapter for API-triggered plan resume."""

    def __init__(self, outbound: OutboundDeliverer):
        self._outbound = outbound

    async def send(self, session_id: str, event: dict) -> None:
        await self._outbound.send_personal(session_id, event)


class PlanResumeService:
    def __init__(
        self,
        task_executor,
        skill_registry=None,
        connection_manager=None,
        channel_router=None,
    ):
        self.task_executor = task_executor
        self.skill_registry = skill_registry
        self.outbound = OutboundDeliverer(
            channel_router=channel_router,
            connection_manager=connection_manager,
        )
        self._running: Set[str] = set()

    async def schedule_resume(self, plan_id: str, plan_store: Optional[PlanStore] = None) -> int:
        store = plan_store or get_plan_store()
        plan = store.get(plan_id)
        if not plan:
            raise ValueError("plan not found")
        if plan.status not in (PlanStatus.FAILED, PlanStatus.EXECUTING):
            raise ValueError(f"plan status {plan.status.value} cannot be retried")
        if plan_id in self._running:
            raise RuntimeError("plan resume already in progress")

        resume_from = store.get_last_done_step(plan_id) + 1
        store.update_status(plan_id, PlanStatus.EXECUTING)
        self._running.add(plan_id)
        asyncio.create_task(self._run(plan_id, store))
        return resume_from

    async def _run(self, plan_id: str, store: PlanStore) -> None:
        plan = store.get(plan_id)
        if not plan:
            return
        channel = SessionOutboundChannel(self.outbound)
        try:
            await self.task_executor.resume(
                plan_id,
                plan.session_id,
                channel,
                workspace_path=plan.workspace_path or ".",
                plan_store=store,
                skill_registry=self.skill_registry,
                audit_store=get_verification_audit_store(),
            )
        except Exception:
            logger.exception("plan resume failed plan_id=%s", plan_id)
            try:
                store.update_status(plan_id, PlanStatus.FAILED)
                await channel.send(plan.session_id, {
                    "type": "plan_resume_failed",
                    "session_id": plan.session_id,
                    "plan_id": plan_id,
                    "message": "计划恢复执行失败",
                })
            except Exception:
                logger.exception("failed to notify plan resume failure plan_id=%s", plan_id)
        finally:
            self._running.discard(plan_id)


_plan_resume_singleton: Optional[PlanResumeService] = None


def init_plan_resume(
    task_executor,
    skill_registry=None,
    connection_manager=None,
    channel_router=None,
) -> PlanResumeService:
    global _plan_resume_singleton
    _plan_resume_singleton = PlanResumeService(
        task_executor,
        skill_registry=skill_registry,
        connection_manager=connection_manager,
        channel_router=channel_router,
    )
    return _plan_resume_singleton


def get_plan_resume() -> Optional[PlanResumeService]:
    return _plan_resume_singleton
