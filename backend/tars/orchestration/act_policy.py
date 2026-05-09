"""ActPolicy — v2.4 执行失败后的结构化决策"""
import asyncio
from enum import Enum


class ActDecision(str, Enum):
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"


class ActPolicy:
    """步骤失败后的决策引擎

    默认策略：自动重试 3 次（指数退避 1s/2s/4s）→ 询问用户 → 超时 abort
    """

    def __init__(self, max_retries: int = 3, backoff_seconds: list = None,
                 user_timeout_s: float = 120):
        self.max_retries = max_retries
        self.backoff = backoff_seconds or [1, 2, 4]
        self.user_timeout_s = user_timeout_s

    def should_retry(self, retries_done: int) -> bool:
        """自动重试判断"""
        return retries_done < self.max_retries

    def backoff_seconds(self, attempt: int) -> float:
        """返回第 attempt 次重试前的等待秒数"""
        idx = min(attempt, len(self.backoff) - 1)
        return self.backoff[idx]

    async def ask_user(self, step: dict, session_id: str, channel) -> ActDecision:
        """向用户询问决策：重试/跳过/中止。

        返回 ActDecision。超时返回 ABORT。
        """
        decision_key = f"{session_id}_{step.get('id', 0)}"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()

        await channel.send(session_id, {
            "type": "plan_step_failed",
            "session_id": session_id,
            "step_id": step.get("id"),
            "description": step.get("description", ""),
            "error": step.get("error", ""),
            "retries": step.get("retries", 0),
            "timestamp": self._now_iso(),
        })

        try:
            decision = await asyncio.wait_for(fut, timeout=self.user_timeout_s)
            return ActDecision(decision) if decision in ("retry", "skip", "abort") else ActDecision.ABORT
        except asyncio.TimeoutError:
            return ActDecision.ABORT

    def store_future(self, session_id: str, step_id: int, fut: asyncio.Future):
        """存储用户决策的 Future（由外部 submit_decision 使用）"""
        pass  # 由 TaskExecutor 管理

    @staticmethod
    def _now_iso():
        from datetime import datetime, timezone, timedelta
        return datetime.now(timezone(timedelta(hours=8))).isoformat()
