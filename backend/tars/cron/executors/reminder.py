"""Cron reminder executor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import CronExecutionContext, CronTaskExecutor


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class ReminderExecutor(CronTaskExecutor):
    task_type = "reminder"

    async def execute(self, ctx: CronExecutionContext, job: Any, config: dict[str, Any]) -> None:
        message = config.get("message") or job.description or job.name
        triggered_at = _now_local()
        session_id = config.get("session_id")
        print(f"[CronRuntime] reminder 开始: job={job.name}, session_id={session_id}")
        event = {
            "type": "cron_reminder",
            "job_id": job.id,
            "session_id": session_id or "default",
            "message": message,
            "timestamp": triggered_at.isoformat(),
        }
        summary_logs = [
            ctx.runtime._build_log_entry("scheduler_matched", "ok", "调度命中"),
            ctx.runtime._build_log_entry("runtime_executing", "ok", "runtime 开始执行 reminder"),
            ctx.runtime._build_log_entry("notification_recorded", "ok", "准备写入 reminder 通知记录"),
        ]

        delivery_status, error_message = await ctx.runtime.deliver_event(
            session_id,
            event,
            summary_logs=summary_logs,
        )

        summary_logs.append(
            ctx.runtime._build_log_entry(
                "delivery_result",
                delivery_status,
                error_message or f"通知投递结果: {delivery_status}",
            )
        )
        ctx.db.create_reminder_notification(
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
        print(f"[CronRuntime] reminder 完成: {delivery_status}")
