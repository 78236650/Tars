"""M4 — Superpowers v4.3.2 full-chain integration tests."""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.config.plan_gate import PlanGateConfig
from tars.config.skills import SkillsConfig
from tars.database.audit_store import VerificationAuditStore
from tars.database.base import Database
from tars.database.plan_store import PlanStore
from tars.orchestration.executor import TaskExecutor
from tars.orchestration.models import PlanCheckpoint, PlanStatus, TaskPlan, TaskStep
from tars.orchestration.plan_gate import PlanGateService
from tars.skills.base import Skill, SkillType, VerifyStep
from tars.skills.intent_extractor import IntentExtractor
from tars.skills.registry import SkillRegistry
from tars.skills.router import SkillRouter
from tars.tools.base import BaseTool, ToolResult
from tars.tools.registry import ToolRegistry


class MockShellTool(BaseTool):
    name = "shell"
    description = "mock shell"

    async def execute(self, **kwargs) -> ToolResult:
        cmd = kwargs.get("command", kwargs.get("cmd", ""))
        return ToolResult(success=True, output=f"ok:{cmd}")


def _deploy_plan(step_count: int = 5) -> TaskPlan:
    return TaskPlan(
        goal="部署服务",
        id=str(uuid.uuid4()),
        session_id="sess-e2e",
        tenant_id="tenant-e2e",
        steps=[
            TaskStep(
                id=i + 1,
                description=f"deploy step {i + 1}",
                tool="shell",
                arguments={"command": f"step{i + 1}"},
            )
            for i in range(step_count)
        ],
    )


def _stack(tmp_path):
    db = Database(str(tmp_path / "e2e.db"))
    plan_store = PlanStore(db)
    plan_store.ensure_schema()
    audit_store = VerificationAuditStore(db)
    audit_store.ensure_schema()
    gate_cfg = PlanGateConfig({
        "enabled": True,
        "auto_approve_threshold": 3,
        "fallback_auto_approve": False,
        "review_timeout_sec": 10,
    })
    gate = PlanGateService(
        plan_store,
        config=gate_cfg,
        connection_manager=MagicMock(session_connections={"sess-e2e": "c1"}),
    )
    registry = ToolRegistry()
    registry.register(MockShellTool())
    deploy_skill = Skill(
        id="deploy",
        name="deploy",
        description="deploy",
        type=SkillType.PROMPT,
        verify=[
            VerifyStep(
                command="echo deploy-verify-ok",
                expect='stdout contains "deploy-verify-ok"',
                timeout_sec=5,
            ),
        ],
        verify_mode="strict",
    )
    skill_registry = SkillRegistry()
    skill_registry.register(deploy_skill)
    executor = TaskExecutor(registry)
    return plan_store, audit_store, gate, executor, skill_registry


class TestScenario1DeployWithReviewAndVerify:
    @pytest.mark.asyncio
    async def test_full_chain(self, tmp_path):
        plan_store, audit_store, gate, executor, skill_registry = _stack(tmp_path)

        reg = SkillRegistry()
        reg.register(Skill(
            id="deploy",
            name="deploy",
            description="deploy",
            type=SkillType.PROMPT,
            triggers=["部署", "deploy", "production"],
        ))
        router = SkillRouter(reg, SkillsConfig({"router": {"enabled": True, "use_embedding": False}}))
        intent = IntentExtractor(use_embedding=False).extract("帮我部署服务")
        assert "deploy" in [c.skill_id for c in router.match(intent, {})]

        plan = _deploy_plan(5)
        plan_store.create(plan)
        channel = MagicMock()
        channel.send = AsyncMock()

        async def approve():
            await asyncio.sleep(0.05)
            gate.approve(plan.id)

        task = asyncio.create_task(approve())
        assert await gate.submit_for_review(plan, channel) is True
        await task
        assert plan_store.get(plan.id).status == PlanStatus.APPROVED

        plan_store.update_status(plan.id, PlanStatus.EXECUTING)
        await executor.execute(
            plan_store.get(plan.id),
            plan.session_id,
            channel,
            workspace_path=str(tmp_path),
            plan_id=plan.id,
            plan_store=plan_store,
            skill_id="deploy",
            skill_registry=skill_registry,
            audit_store=audit_store,
        )
        assert plan_store.get(plan.id).status == PlanStatus.DONE
        audit = audit_store.latest_for_plan(plan.id)
        assert audit is not None
        assert audit["passed"] is True
        events = [call.args[1].get("type") for call in channel.send.call_args_list]
        assert "verification_complete" in events


class TestScenario2VerifyFailure:
    @pytest.mark.asyncio
    async def test_verify_fail_blocks_done(self, tmp_path):
        plan_store, audit_store, _gate, executor, skill_registry = _stack(tmp_path)
        skill_registry.unregister("deploy")
        skill_registry.register(Skill(
            id="deploy",
            name="deploy",
            description="deploy",
            type=SkillType.PROMPT,
            verify=[VerifyStep(command="exit 1", expect="exit_code == 0", timeout_sec=3)],
            verify_mode="strict",
        ))

        plan = _deploy_plan(2)
        plan_store.create(plan)
        channel = MagicMock()
        channel.send = AsyncMock()
        plan_store.update_status(plan.id, PlanStatus.EXECUTING)

        await executor.execute(
            plan,
            plan.session_id,
            channel,
            workspace_path=str(tmp_path),
            plan_id=plan.id,
            plan_store=plan_store,
            skill_id="deploy",
            skill_registry=skill_registry,
            audit_store=audit_store,
        )
        assert plan_store.get(plan.id).status == PlanStatus.FAILED
        audit = audit_store.latest_for_plan(plan.id)
        assert audit["passed"] is False
        events = [call.args[1].get("type") for call in channel.send.call_args_list]
        assert "verification_failed" in events

    @pytest.mark.asyncio
    async def test_resume_after_partial_execution(self, tmp_path):
        plan_store, _audit_store, _gate, executor, skill_registry = _stack(tmp_path)
        skill_registry.unregister("deploy")
        skill_registry.register(Skill(
            id="deploy",
            name="deploy",
            description="deploy",
            type=SkillType.PROMPT,
            verify=[],
        ))
        plan = _deploy_plan(3)
        plan_store.create(plan)
        plan_store.update_status(plan.id, PlanStatus.EXECUTING)
        plan_store.add_checkpoint(PlanCheckpoint(
            plan_id=plan.id,
            step_id=1,
            status="done",
            output="step1 ok",
            timestamp="2026-05-25T00:00:00+08:00",
        ))
        channel = MagicMock()
        channel.send = AsyncMock()
        await executor.resume(
            plan.id,
            plan.session_id,
            channel,
            workspace_path=str(tmp_path),
            plan_store=plan_store,
        )
        assert plan_store.get_last_done_step(plan.id) >= 2


class TestScenario3AutoApproveSimplePlan:
    @pytest.mark.asyncio
    async def test_two_step_skips_review(self, tmp_path):
        db = Database(str(tmp_path / "auto.db"))
        plan_store = PlanStore(db)
        plan_store.ensure_schema()
        gate = PlanGateService(
            plan_store,
            config=PlanGateConfig({"enabled": True, "auto_approve_threshold": 3}),
            connection_manager=MagicMock(session_connections={"sess-e2e": "c1"}),
        )
        plan = TaskPlan(
            goal="简单任务",
            id=str(uuid.uuid4()),
            session_id="sess-e2e",
            steps=[
                TaskStep(id=1, description="search", tool="knowledge_search", arguments={}),
                TaskStep(id=2, description="calc", tool="calculator", arguments={}),
            ],
        )
        plan_store.create(plan)
        channel = MagicMock()
        channel.send = AsyncMock()
        ok = await gate.submit_for_review(plan, channel)
        assert ok is True
        assert plan_store.get(plan.id).status == PlanStatus.APPROVED
        events = [call.args[1].get("type") for call in channel.send.call_args_list]
        assert "plan_review_request" not in events
