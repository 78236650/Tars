import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class FakeCronRuntime:
    def __init__(self):
        self.synced = []
        self.unscheduled = []
        self.loaded = False

    async def load_from_db(self):
        self.loaded = True

    async def sync_job(self, job_id: str):
        self.synced.append(job_id)

    def unschedule_job(self, job_id: str):
        self.unscheduled.append(job_id)


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from tars.database import Database
    import tars.main as main

    test_db = Database(db_path=str(tmp_path / "t.db"))
    fake_runtime = FakeCronRuntime()

    main.db = test_db
    main.cron_runtime = fake_runtime
    main.cronjob_tool.db = test_db
    main.cronjob_tool.set_runtime(fake_runtime)

    with TestClient(main.app) as test_client:
        yield test_client, test_db

    test_db.close()


def _create_notification(db, job, *, message: str, session_id: str | None, status: str):
    return db.create_reminder_notification(
        user_id=job.user_id,
        job_id=job.id,
        session_id=session_id,
        task_name=job.name,
        message=message,
        delivery_status=status,
        error_message="缺少 session_id，回退广播路径" if status == "broadcast" else None,
        summary_logs=[
            {"step": "scheduler_matched", "status": "ok", "message": "调度命中"},
            {"step": "delivery_result", "status": status, "message": status},
        ],
    )


def test_reminder_notifications_api_supports_list_detail_and_mark_read(client):
    http, db = client
    job = db.create_cronjob(
        user_id="default",
        name="喝水提醒",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config=json.dumps({"message": "记得喝水", "session_id": "session-a"}),
    )
    older = _create_notification(
        db,
        job,
        message="第一次提醒",
        session_id="session-a",
        status="delivered",
    )
    latest = _create_notification(
        db,
        job,
        message="第二次提醒",
        session_id=None,
        status="broadcast",
    )

    list_resp = http.get("/api/reminder-notifications")
    assert list_resp.status_code == 200
    payload = list_resp.json()["data"]
    assert payload["total"] == 2
    assert payload["unread_total"] == 2
    assert [item["id"] for item in payload["notifications"]] == [latest.id, older.id]
    assert payload["notifications"][0]["delivery_status"] == "broadcast"
    assert payload["notifications"][0]["is_read"] is False

    detail_resp = http.get(f"/api/reminder-notifications/{latest.id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["job_id"] == job.id
    assert detail["session_id"] is None
    assert detail["summary_logs"][0]["step"] == "scheduler_matched"

    read_resp = http.post(f"/api/reminder-notifications/{latest.id}/read")
    assert read_resp.status_code == 200
    read_payload = read_resp.json()["data"]
    assert read_payload["id"] == latest.id
    assert read_payload["is_read"] is True
    assert read_payload["read_at"] is not None

    updated_list = http.get("/api/reminder-notifications").json()["data"]
    assert updated_list["unread_total"] == 1
    assert updated_list["notifications"][0]["is_read"] is True


def test_cronjob_api_includes_latest_notification_status(client):
    http, db = client
    job = db.create_cronjob(
        user_id="default",
        name="站起来活动",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config=json.dumps({"message": "起来活动一下"}),
    )
    _create_notification(
        db,
        job,
        message="起来活动一下",
        session_id=None,
        status="broadcast",
    )

    list_resp = http.get("/api/cronjobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()["data"]["jobs"]
    assert jobs[0]["latest_notification"]["job_id"] == job.id
    assert jobs[0]["latest_notification"]["delivery_status"] == "broadcast"
    assert jobs[0]["latest_notification"]["error_message"] == "缺少 session_id，回退广播路径"

    detail_resp = http.get(f"/api/cronjobs/{job.id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["latest_notification"]["id"] is not None
    assert detail["latest_notification"]["message"] == "起来活动一下"
