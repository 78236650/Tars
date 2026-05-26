"""Plan retry API → TaskExecutor.resume wiring."""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.config.plan_gate import PlanGateConfig
from tars.database.audit_store import VerificationAuditStore
from tars.database.base import Database
from tars.database.plan_store import PlanStore
from tars.orchestration.executor import TaskExecutor
from tars.orchestration.models import PlanCheckpoint, PlanStatus, TaskPlan, TaskStep
from tars.orchestration.plan_gate import PlanGateService
from tars.orchestration.plan_resume import PlanResumeService
from tars.skills.base import Skill, SkillType
from tars.skills.registry import SkillRegistry
from tars.tools.base import BaseTool, ToolResult
from tars.tools.registry import ToolRegistry


class MockShellTool(BaseTool):
    name = "shell"
    description = "mock shell"

    async def execute(self, **kwargs) -> ToolResult:
        cmd = kwargs.get("command", kwargs.get("cmd", ""))
        return ToolResult(success=True, output=f"ok:{cmd}")


class FakeConnectionManager:
    def __init__(self):
        self.session_connections = {}
        self.events = []

    async def deliver_to_session(self, session_id: str, event: dict) -> bool:
        self.events.append((session_id, event))
        return True

    async def send_personal_message(self, session_id: str, event: dict) -> bool:
        return await self.deliver_to_session(session_id, event)


@pytest.mark.asyncio
async def test_retry_api_schedules_executor_resume(tmp_path):
    db = Database(str(tmp_path / "retry.db"))
    plan_store = PlanStore(db)
    plan_store.ensure_schema()
    audit_store = VerificationAuditStore(db)
    audit_store.ensure_schema()

    registry = ToolRegistry()
    registry.register(MockShellTool())
    executor = TaskExecutor(registry)
    skill_registry = SkillRegistry()
    skill_registry.register(Skill(id="deploy", name="deploy", description="d", type=SkillType.PROMPT))

    cm = FakeConnectionManager()
    cm.session_connections["sess-retry"] = "conn-1"
    resume_svc = PlanResumeService(
        executor,
        skill_registry=skill_registry,
        connection_manager=cm,
    )

    plan = TaskPlan(
        goal="retry me",
        id=str(uuid.uuid4()),
        session_id="sess-retry",
        tenant_id="default",
        skill_id="deploy",
        steps=[
            TaskStep(id=1, description="s1", tool="shell", arguments={"command": "a"}),
            TaskStep(id=2, description="s2", tool="shell", arguments={"command": "b"}),
            TaskStep(id=3, description="s3", tool="shell", arguments={"command": "c"}),
        ],
    )
    plan_store.create(plan)
    plan_store.update_status(plan.id, PlanStatus.FAILED)
    plan_store.add_checkpoint(PlanCheckpoint(
        plan_id=plan.id,
        step_id=1,
        status="done",
        output="ok",
        timestamp="2026-05-25T00:00:00+08:00",
    ))

    resume_from = await resume_svc.schedule_resume(plan.id, plan_store)
    assert resume_from == 2
    await asyncio.sleep(0.2)

    assert plan_store.get(plan.id).status == PlanStatus.DONE
    assert plan_store.get_last_done_step(plan.id) >= 2
    event_types = [e[1].get("type") for e in cm.events]
    assert "plan_complete" in event_types


@pytest.mark.asyncio
async def test_retry_rejects_non_failed_status(tmp_path):
    db = Database(str(tmp_path / "retry2.db"))
    plan_store = PlanStore(db)
    plan_store.ensure_schema()
    executor = TaskExecutor(ToolRegistry())
    resume_svc = PlanResumeService(executor, connection_manager=FakeConnectionManager())

    plan = TaskPlan(
        goal="draft",
        id=str(uuid.uuid4()),
        session_id="s1",
        steps=[TaskStep(id=1, description="s", tool="shell", arguments={})],
    )
    plan_store.create(plan)

    with pytest.raises(ValueError, match="cannot be retried"):
        await resume_svc.schedule_resume(plan.id, plan_store)
