"""LLM rate limiter — v4.0.0 Phase 2.

Per-user fair scheduling with asyncio.Semaphore-based concurrency control.
"""
import asyncio
import threading
from collections import defaultdict
from typing import Optional


class LLMRateLimiter:
    """Limits concurrent LLM calls with per-user fairness.

    - Global semaphore caps total concurrent calls.
    - Per-user counter caps each user's share.
    - FIFO queue with configurable timeout.
    """

    def __init__(
        self,
        max_concurrent: int = 2,
        per_user_max: int = 1,
        queue_timeout: float = 60.0,
    ):
        self._max_concurrent = max_concurrent
        self._per_user_max = per_user_max
        self._queue_timeout = queue_timeout

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._user_counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    async def acquire(self, user_id: str, pool_key: str = "default") -> bool:
        """Try to acquire a slot. Returns True on success, False on timeout.

        v5.0.5/A7: pool_key 现真正生效 —— per-user 配额按 (pool_key, user_id)
        独立计数,使不同池(如交互 vs 后台批处理)互不挤占对方的用户配额。
        """
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._queue_timeout,
            )
        except asyncio.TimeoutError:
            return False

        if not acquired:
            return False

        count_key = (pool_key, user_id)
        with self._lock:
            if self._user_counts.get(count_key, 0) >= self._per_user_max:
                self._semaphore.release()
                return False
            self._user_counts[count_key] += 1

        return True

    def release(self, user_id: str, pool_key: str = "default"):
        """Release a slot. Thread-safe per-(pool,user) count decrement."""
        self._semaphore.release()
        count_key = (pool_key, user_id)
        with self._lock:
            if self._user_counts.get(count_key, 0) > 0:
                self._user_counts[count_key] -= 1
                if self._user_counts[count_key] <= 0:
                    self._user_counts.pop(count_key, None)

    def stats(self) -> dict:
        """Return current limiter statistics."""
        return {
            "max_concurrent": self._max_concurrent,
            "per_user_max": self._per_user_max,
            "queue_timeout": self._queue_timeout,
            "available_slots": self._semaphore._value,
            "active_users": len(self._user_counts),
            "user_counts": {f"{pool}:{uid}": c for (pool, uid), c in self._user_counts.items()},
        }

    @property
    def waiting(self) -> int:
        """Estimated number of waiters."""
        return max(0, self._max_concurrent - self._semaphore._value)


# ── Global singleton ────────────────────────────────────────────────

rate_limiter: Optional[LLMRateLimiter] = None


def init_rate_limiter(
    max_concurrent: int = 2,
    per_user_max: int = 1,
    queue_timeout: float = 60.0,
) -> LLMRateLimiter:
    global rate_limiter
    rate_limiter = LLMRateLimiter(max_concurrent, per_user_max, queue_timeout)
    return rate_limiter
