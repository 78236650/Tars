from datetime import datetime

import pytest

from tars.database import Database
from tars.scheduler import CronExpression
from tars.tools.builtin.cronjob import CronJobTool


class FakeScheduler:
    def __init__(self):
        self.added = {}
        self.removed = []

    def add_task(self, name, cron_expression, task, task_id=None):
        self.added[task_id or name] = {
            "name": name,
            "cron_expression": cron_expression,
            "task": task,
            "task_id": task_id,
        }
        return task_id or name

    def remove_task(self, task_id):
        self.removed.append(task_id)
        self.added.pop(task_id, None)


class FakeConnectionManager:
    def __init__(self):
        self.events = []
        self.personal = []

    async def broadcast(self, event):
        self.events.append(event)

    async def send_personal_message(self, session_id, event):
        self.personal.append((session_id, event))
        return True


class FailingConnectionManager(FakeConnectionManager):
    async def send_personal_message(self, session_id, event):
        raise RuntimeError("socket closed")


def test_cron_expression_supports_specific_time():
    expr = CronExpression("5 14 * * *")

    result = expr.next_run(datetime(2026, 5, 16, 14, 4, 0))
    assert result == datetime(2026, 5, 16, 14, 5, 0)

    next_day = expr.next_run(datetime(2026, 5, 16, 14, 5, 0))
    assert next_day == datetime(2026, 5, 17, 14, 5, 0)


@pytest.mark.asyncio
async def test_cron_runtime_loads_enabled_jobs_from_db(tmp_path):
    from tars.cron.runtime import CronRuntime

    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="喝水提醒",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config='{"message":"记得喝水"}',
    )

    runtime = CronRuntime(
        db=db,
        scheduler=FakeScheduler(),
        connection_manager=FakeConnectionManager(),
    )
    await runtime.load_from_db()

    assert job.id in runtime.scheduler.added
    loaded = db.get_cronjob(job.id)
    assert loaded.next_run is not None


@pytest.mark.asyncio
async def test_cron_runtime_executes_reminder_and_broadcasts(tmp_path):
    from tars.cron.runtime import CronRuntime

    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="站起来活动",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config='{"message":"起来活动一下"}',
    )
    cm = FakeConnectionManager()
    runtime = CronRuntime(db=db, scheduler=FakeScheduler(), connection_manager=cm)

    await runtime.execute_job(job.id)

    assert cm.events
    assert cm.events[0]["type"] == "cron_reminder"
    assert "起来活动一下" in cm.events[0]["message"]
    updated = db.get_cronjob(job.id)
    assert updated.last_run is not None
    notifications = db.list_reminder_notifications("default")
    assert len(notifications) == 1
    assert notifications[0].job_id == job.id
    assert notifications[0].delivery_status == "broadcast"
    assert notifications[0].is_read is False
    assert notifications[0].error_message == "缺少 session_id，回退广播路径"


@pytest.mark.asyncio
async def test_cron_runtime_sends_reminder_to_session_only(tmp_path):
    from tars.cron.runtime import CronRuntime

    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="会议提醒",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config='{"message":"开会","session_id":"session-a"}',
    )
    cm = FakeConnectionManager()
    runtime = CronRuntime(db=db, scheduler=FakeScheduler(), connection_manager=cm)

    await runtime.execute_job(job.id)

    assert cm.personal and cm.personal[0][0] == "session-a"
    assert cm.events == []
    notifications = db.list_reminder_notifications("default")
    assert len(notifications) == 1
    assert notifications[0].session_id == "session-a"
    assert notifications[0].delivery_status == "delivered"
    assert [entry["step"] for entry in notifications[0].summary_logs] == [
        "scheduler_matched",
        "runtime_executing",
        "notification_recorded",
        "websocket_delivery_attempted",
        "delivery_result",
    ]


@pytest.mark.asyncio
async def test_cron_runtime_records_failed_delivery_status(tmp_path):
    from tars.cron.runtime import CronRuntime

    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="失败提醒",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config='{"message":"发送失败","session_id":"session-a"}',
    )
    runtime = CronRuntime(
        db=db,
        scheduler=FakeScheduler(),
        connection_manager=FailingConnectionManager(),
    )

    await runtime.execute_job(job.id)

    notifications = db.list_reminder_notifications("default")
    assert len(notifications) == 1
    assert notifications[0].delivery_status == "failed"
    assert notifications[0].error_message == "socket closed"
    assert notifications[0].session_id == "session-a"


@pytest.mark.asyncio
async def test_cronjob_tool_create_syncs_runtime(tmp_path):
    class FakeRuntime:
        def __init__(self):
            self.synced = []

        async def sync_job(self, job_id):
            self.synced.append(job_id)

    db = Database(db_path=str(tmp_path / "cron.db"))
    runtime = FakeRuntime()
    tool = CronJobTool(db=db, cron_runtime=runtime)

    result = await tool.execute(
        action="create",
        name="提醒我",
        cron="5 14 * * *",
        task_type="reminder",
        task_config={"message": "到了"},
    )

    assert result.success is True
    assert runtime.synced == [result.metadata["job_id"]]


@pytest.mark.asyncio
async def test_cronjob_tool_create_injects_session_id(tmp_path):
    class FakeRuntime:
        async def sync_job(self, job_id):
            return None

    db = Database(db_path=str(tmp_path / "cron.db"))
    tool = CronJobTool(db=db, cron_runtime=FakeRuntime())

    await tool.execute(
        action="create",
        name="提醒我",
        cron="5 14 * * *",
        task_type="reminder",
        task_config={"message": "到了"},
        session_id="session-a",
    )

    job = db.get_user_cronjobs("default")[0]
    config = __import__("json").loads(job.task_config)
    assert config["session_id"] == "session-a"
