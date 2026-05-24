"""Cron delegate + prompt executor tests."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.cron.runtime import CronRuntime
from tars.database import Database


class FakeScheduler:
    def add_task(self, *args, **kwargs):
        return kwargs.get("task_id")

    def remove_task(self, task_id):
        return None


class FakeConnectionManager:
    def __init__(self):
        self.personal = []
        self.events = []

    async def send_personal_message(self, session_id, event):
        self.personal.append((session_id, event))
        return True

    async def broadcast(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_delegate_executor_invokes_subagent_and_emits_event(tmp_path):
    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="code review",
        cron_expression="5 14 * * *",
        task_type="delegate",
        task_config='{"subagent_type":"code","task":"review sql","session_id":"sess-d1"}',
    )

    agent = MagicMock()
    agent.subagent_manager = MagicMock()
    agent.subagent_manager.invoke_subagent = AsyncMock(return_value="review done")

    cm = FakeConnectionManager()
    runtime = CronRuntime(db=db, scheduler=FakeScheduler(), connection_manager=cm, agent=agent)

    await runtime.execute_job(job.id)

    agent.subagent_manager.invoke_subagent.assert_awaited_once()
    assert cm.personal
    _sid, event = cm.personal[-1]
    assert event["type"] == "cron_delegate_result"
    assert event["result"] == "review done"
    assert event["subagent_type"] == "code"


@pytest.mark.asyncio
async def test_prompt_executor_runs_agent_turn_on_session(tmp_path):
    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="daily summary",
        cron_expression="5 14 * * *",
        task_type="prompt",
        task_config='{"prompt":"总结今日待办","session_id":"sess-p1"}',
    )

    agent = MagicMock()
    agent.handle_message = AsyncMock()

    cm = FakeConnectionManager()
    runtime = CronRuntime(db=db, scheduler=FakeScheduler(), connection_manager=cm, agent=agent)

    await runtime.execute_job(job.id)

    agent.handle_message.assert_awaited_once()
    kwargs = agent.handle_message.await_args.kwargs
    assert kwargs["session_id"] == "sess-p1"
    assert kwargs["user_content"] == "总结今日待办"
    assert kwargs["request_context"]["transport"] == "cron"

    complete_events = [e for _s, e in cm.personal if e.get("type") == "cron_prompt_complete"]
    assert complete_events
    assert complete_events[0]["job_id"] == job.id


@pytest.mark.asyncio
async def test_cron_execute_writes_audit_log(tmp_path):
    from tars.security.audit import init_audit_logger

    db = Database(db_path=str(tmp_path / "cron.db"))
    init_audit_logger(db)
    job = db.create_cronjob(
        user_id="default",
        name="delegate audit",
        cron_expression="5 14 * * *",
        task_type="delegate",
        task_config='{"subagent_type":"writing","task":"draft","session_id":"s1"}',
    )

    agent = MagicMock()
    agent.subagent_manager = MagicMock()
    agent.subagent_manager.invoke_subagent = AsyncMock(return_value="ok")

    runtime = CronRuntime(
        db=db,
        scheduler=FakeScheduler(),
        connection_manager=FakeConnectionManager(),
        agent=agent,
    )
    await runtime.execute_job(job.id)

    logs, _total = db.list_audit_logs(action="cron_execute")
    assert logs
    assert logs[0].action == "cron_execute"
    assert logs[0].resource_id == job.id
