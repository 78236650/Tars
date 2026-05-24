"""Cron prompt executor — inject a prompt and run one agent turn."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ...channels.base import Channel, ChannelMessage
from .base import CronExecutionContext, CronTaskExecutor


def _now_local() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class CronPromptChannel(Channel):
    """Minimal Channel that forwards agent outbound events to a cron session."""

    def __init__(self, connection_manager, session_id: str):
        self._connection_manager = connection_manager
        self._session_id = session_id

    async def receive(self, raw_message: Any) -> ChannelMessage:
        return ChannelMessage(
            channel="cron",
            user_id="default",
            session_id=self._session_id,
            content=str(raw_message or ""),
            timestamp=_now_local(),
        )

    async def send(self, session_id: str, event: dict) -> None:
        sid = session_id or self._session_id
        await self._connection_manager.send_personal_message(sid, event)

    async def stream(self, session_id: str, chunk: str) -> None:
        await self.send(
            session_id,
            {
                "type": "text_chunk",
                "session_id": session_id or self._session_id,
                "content": chunk,
                "timestamp": _now_local().isoformat(),
            },
        )


class PromptExecutor(CronTaskExecutor):
    task_type = "prompt"

    async def execute(self, ctx: CronExecutionContext, job: Any, config: dict[str, Any]) -> None:
        if ctx.agent is None:
            raise RuntimeError("Agent 未配置，无法执行 prompt 定时任务")

        prompt = config.get("prompt") or job.description or job.name
        session_id = config.get("session_id")
        if not session_id:
            await ctx.runtime.deliver_event(
                None,
                {
                    "type": "cron_prompt_error",
                    "job_id": job.id,
                    "message": "prompt cron 缺少 session_id",
                    "timestamp": _now_local().isoformat(),
                },
            )
            raise ValueError("prompt cron 缺少 session_id")

        channel = CronPromptChannel(ctx.connection_manager, session_id)

        await ctx.agent.handle_message(
            session_id=session_id,
            user_content=prompt,
            channel=channel,
            request_context={
                "transport": "cron",
                "user_id": job.user_id or "default",
                "cron_job_id": job.id,
            },
        )

        await ctx.runtime.deliver_event(
            session_id,
            {
                "type": "cron_prompt_complete",
                "job_id": job.id,
                "session_id": session_id,
                "timestamp": _now_local().isoformat(),
            },
        )
