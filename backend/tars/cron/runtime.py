import json
from datetime import datetime, timedelta, timezone
from typing import Any

from ..scheduler import CronExpression


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class CronRuntime:
    """负责将 DB 中的 cronjob 同步到 scheduler，并执行 reminder。"""

    def __init__(self, db, scheduler, connection_manager):
        self.db = db
        self.scheduler = scheduler
        self.connection_manager = connection_manager

    async def load_from_db(self) -> None:
        for job in self.db.get_enabled_cronjobs():
            await self.sync_job(job.id)

    async def sync_job(self, job_id: str) -> None:
        job = self.db.get_cronjob(job_id)
        if not job or not job.enabled:
            self.unschedule_job(job_id)
            return

        self.unschedule_job(job_id)
        next_run = CronExpression(job.cron_expression).next_run()
        self.db.update_cronjob(job.id, next_run=next_run)

        async def runner(current_job_id: str = job.id):
            await self.execute_job(current_job_id)

        self.scheduler.add_task(
            name=job.name,
            cron_expression=job.cron_expression,
            task=runner,
            task_id=job.id,
        )

    def unschedule_job(self, job_id: str) -> None:
        self.scheduler.remove_task(job_id)

    async def execute_job(self, job_id: str) -> None:
        job = self.db.get_cronjob(job_id)
        if not job or not job.enabled:
            self.unschedule_job(job_id)
            return

        config = self._load_config(job.task_config)
        if job.task_type == "reminder":
            await self._run_reminder(job, config)
        else:
            print(f"[CronRuntime] 未实现的任务类型: {job.task_type}")

        now = _now_local()
        next_run = CronExpression(job.cron_expression).next_run(now)
        self.db.update_cronjob(job.id, last_run=now, next_run=next_run)

    def _load_config(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def _run_reminder(self, job, config: dict[str, Any]) -> None:
        message = config.get("message") or job.description or job.name
        triggered_at = _now_local()
        session_id = config.get("session_id")
        print(f"[CronRuntime] _run_reminder 开始: job={job.name}, session_id={session_id}")
        event = {
            "type": "cron_reminder",
            "job_id": job.id,
            "session_id": session_id or "default",
            "message": message,
            "timestamp": triggered_at.isoformat(),
        }
        summary_logs = [
            self._build_log_entry("scheduler_matched", "ok", "调度命中"),
            self._build_log_entry("runtime_executing", "ok", "runtime 开始执行 reminder"),
            self._build_log_entry("notification_recorded", "ok", "准备写入 reminder 通知记录"),
        ]

        delivery_status = "failed"
        error_message = None

        if session_id:
            summary_logs.append(
                self._build_log_entry(
                    "websocket_delivery_attempted",
                    "ok",
                    f"向会话 {session_id} 投递通知",
                )
            )
            try:
                print(f"[CronRuntime] 尝试 send_personal_message: {session_id}")
                delivered = await self.connection_manager.send_personal_message(session_id, event)
                if delivered:
                    delivery_status = "delivered"
                    print(f"[CronRuntime] 投递成功")
                else:
                    summary_logs.append(
                        self._build_log_entry("websocket_delivery_attempted", "broadcast", "会话连接不存在，回退广播")
                    )
                    print(f"[CronRuntime] 会话不存在，回退 broadcast")
                    await self.connection_manager.broadcast(event)
                    delivery_status = "broadcast"
                    print(f"[CronRuntime] broadcast 完成")
            except Exception as exc:
                error_message = str(exc)
                print(f"[CronRuntime] 投递异常: {error_message}")
        else:
            error_message = "缺少 session_id，回退广播路径"
            summary_logs.append(
                self._build_log_entry("websocket_delivery_attempted", "broadcast", "通过 broadcast 投递通知")
            )
            try:
                print(f"[CronRuntime] 无 session_id，执行 broadcast")
                await self.connection_manager.broadcast(event)
                delivery_status = "broadcast"
                print(f"[CronRuntime] broadcast 完成")
            except Exception as exc:
                error_message = str(exc)
                print(f"[CronRuntime] broadcast 异常: {error_message}")

        print(f"[CronRuntime] 写入通知记录...")
        summary_logs.append(
            self._build_log_entry(
                "delivery_result",
                delivery_status,
                error_message or f"通知投递结果: {delivery_status}",
            )
        )
        self.db.create_reminder_notification(
            user_id=job.user_id,
            job_id=job.id,
            session_id=session_id,
            task_name=job.name,
            message=message,
            delivery_status=delivery_status,
            error_message=error_message,
            summary_logs=summary_logs,
            triggered_at=triggered_at,
        )
        print(f"[CronRuntime] _run_reminder 完成: {delivery_status}")

    def _build_log_entry(self, step: str, status: str, message: str) -> dict[str, str]:
        return {
            "step": step,
            "status": status,
            "message": message,
            "timestamp": _now_local().isoformat(),
        }
