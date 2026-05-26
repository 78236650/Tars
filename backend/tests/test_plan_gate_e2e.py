"""M2 — Plan approval gate tests"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.config.plan_gate import PlanGateConfig
from tars.database.base import Database
from tars.database.plan_store import PlanStore
from tars.orchestration.models import (
    PlanStatus,
    TaskPlan,
    TaskStep,
    auto_approve_eligible,
)
from tars.orchestration.plan_gate import PlanGateService


def _plan(steps):
    return TaskPlan(
        goal="test goal",
        steps=[
            TaskStep(id=i + 1, description=f"step {i+1}", tool=tool)
            for i, tool in enumerate(steps)
        ],
    )


class TestAutoApproveEligible:
    def test_two_safe_steps_auto_approve(self):
        plan = _plan(["knowledge_search", "calculator"])
        cfg = PlanGateConfig({"enabled": True, "auto_approve_threshold": 3})
        assert auto_approve_eligible(plan, cfg) is True

    def test_three_dangerous_steps_need_review(self):
        plan = _plan(["shell", "file_write", "network"])
        cfg = PlanGateConfig({"enabled": True, "auto_approve_threshold": 3})
        assert auto_approve_eligible(plan, cfg) is False

    def test_five_safe_steps_need_review(self):
        plan = _plan(["a", "b", "c", "d", "e"])
        cfg = PlanGateConfig({"enabled": True, "auto_approve_threshold": 3})
        assert auto_approve_eligible(plan, cfg) is False

    def test_always_approve_blocks_auto(self):
        plan = _plan(["calculator"])
        cfg = PlanGateConfig({"enabled": True, "always_approve": True})
        assert auto_approve_eligible(plan, cfg) is False

    def test_gate_disabled_auto_approves(self):
        plan = _plan(["shell", "shell", "shell", "shell", "shell"])
        cfg = PlanGateConfig({"enabled": False})
        assert auto_approve_eligible(plan, cfg) is True


class TestPlanStore:
    def test_create_and_checkpoint(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        store = PlanStore(db)
        store.ensure_schema()

        plan = _plan(["shell"])
        plan.id = "plan-1"
        plan.session_id = "sess-1"
        plan.tenant_id = "tenant-1"
        store.create(plan)

        fetched = store.get("plan-1")
        assert fetched is not None
        assert fetched.goal == "test goal"
        assert fetched.status == PlanStatus.DRAFT

        store.update_status("plan-1", PlanStatus.EXECUTING)
        from tars.orchestration.models import PlanCheckpoint
        store.add_checkpoint(PlanCheckpoint(
            plan_id="plan-1",
            step_id=1,
            status="done",
            output="ok",
            timestamp="2026-05-25T00:00:00+08:00",
        ))
        assert store.get_last_done_step("plan-1") == 1
        detail = store.get_detail("plan-1")
        assert len(detail["checkpoints"]) == 1


class TestPlanGateService:
    @pytest.mark.asyncio
    async def test_auto_approve_skips_wait(self, tmp_path):
        db = Database(str(tmp_path / "gate.db"))
        store = PlanStore(db)
        store.ensure_schema()
        cfg = PlanGateConfig({
            "enabled": True,
            "auto_approve_threshold": 3,
            "review_timeout_sec": 2,
        })
        gate = PlanGateService(store, config=cfg)
        plan = _plan(["calculator"])
        plan.id = "p-auto"
        plan.session_id = "s1"
        store.create(plan)

        channel = MagicMock()
        channel.send = AsyncMock()
        ok = await gate.submit_for_review(plan, channel)
        assert ok is True
        assert store.get("p-auto").status == PlanStatus.APPROVED
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_approve_via_api(self, tmp_path):
        db = Database(str(tmp_path / "gate2.db"))
        store = PlanStore(db)
        store.ensure_schema()
        cfg = PlanGateConfig({
            "enabled": True,
            "auto_approve_threshold": 1,
            "review_timeout_sec": 5,
            "fallback_auto_approve": False,
        })
        gate = PlanGateService(store, config=cfg, connection_manager=MagicMock(session_connections={"s1": "c1"}))
        plan = _plan(["shell", "shell", "shell"])
        plan.id = "p-manual"
        plan.session_id = "s1"
        store.create(plan)

        channel = MagicMock()
        channel.send = AsyncMock()

        async def approve_later():
            await asyncio.sleep(0.05)
            gate.approve("p-manual")

        task = asyncio.create_task(approve_later())
        ok = await gate.submit_for_review(plan, channel)
        await task
        assert ok is True
        assert store.get("p-manual").status == PlanStatus.APPROVED
        assert any(
            call.args[1].get("type") == "plan_review_request"
            for call in channel.send.call_args_list
        )

    @pytest.mark.asyncio
    async def test_reject_cancels_wait(self, tmp_path):
        db = Database(str(tmp_path / "gate3.db"))
        store = PlanStore(db)
        store.ensure_schema()
        cfg = PlanGateConfig({
            "enabled": True,
            "auto_approve_threshold": 1,
            "review_timeout_sec": 5,
            "fallback_auto_approve": False,
        })
        gate = PlanGateService(store, config=cfg, connection_manager=MagicMock(session_connections={"s1": "c1"}))
        plan = _plan(["shell", "shell", "shell"])
        plan.id = "p-reject"
        plan.session_id = "s1"
        store.create(plan)

        channel = MagicMock()
        channel.send = AsyncMock()

        async def reject_later():
            await asyncio.sleep(0.05)
            gate.reject("p-reject")

        task = asyncio.create_task(reject_later())
        ok = await gate.submit_for_review(plan, channel)
        await task
        assert ok is False
        assert store.get("p-reject").status == PlanStatus.REJECTED
