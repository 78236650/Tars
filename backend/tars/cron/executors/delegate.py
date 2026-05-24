"""Cron delegate executor — run a subagent task and push result over WS."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import CronExecutionContext, CronTaskExecutor


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class DelegateExecutor(CronTaskExecutor):
    task_type = "delegate"

    async def execute(self, ctx: CronExecutionContext, job: Any, config: dict[str, Any]) -> None:
        if ctx.agent is None:
            raise RuntimeError("Agent 未配置，无法执行 delegate 定时任务")

        task = config.get("task") or job.description or job.name
        session_id = config.get("session_id") or "default"
        subagent_type = config.get("subagent_type")
        manager = ctx.agent.subagent_manager

        if subagent_type:
            result = await manager.invoke_subagent(subagent_type, task, context={"session_id": session_id})
        else:
            result = await manager.delegate_task(task, context={"session_id": session_id})

        event = {
            "type": "cron_delegate_result",
            "job_id": job.id,
            "session_id": session_id,
            "subagent_type": subagent_type,
            "task": task,
            "result": result,
            "timestamp": _now_local().isoformat(),
        }
        await ctx.runtime.deliver_event(session_id, event)
