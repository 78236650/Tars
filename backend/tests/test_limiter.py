"""Tests for TARS rate limiter — Phase 2 Task 8."""
import pytest
import asyncio
from tars.concurrency.limiter import LLMRateLimiter


class TestRateLimiter:
    """Verify per-user concurrency limits and fairness."""

    @pytest.mark.asyncio
    async def test_acquire_release_single(self):
        limiter = LLMRateLimiter(max_concurrent=2, per_user_max=1)
        ok = await limiter.acquire("u1")
        assert ok
        limiter.release("u1")

    @pytest.mark.asyncio
    async def test_acquire_up_to_limit(self):
        limiter = LLMRateLimiter(max_concurrent=2, per_user_max=1)
        ok1 = await limiter.acquire("u1")
        ok2 = await limiter.acquire("u2")
        assert ok1 and ok2
        limiter.release("u1")
        limiter.release("u2")

    @pytest.mark.asyncio
    async def test_block_when_full(self):
        limiter = LLMRateLimiter(max_concurrent=1, per_user_max=1)
        ok1 = await limiter.acquire("u1")
        assert ok1
        # Second acquire should timeout quickly
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(limiter.acquire("u2"), timeout=0.1)
        # But should work after release
        limiter.release("u1")

    @pytest.mark.asyncio
    async def test_per_user_limit(self):
        limiter = LLMRateLimiter(max_concurrent=5, per_user_max=1)
        ok1 = await limiter.acquire("u1")
        ok2 = await limiter.acquire("u1")  # Same user, exceeds per_user_max
        assert ok1
        assert not ok2  # Should be denied
        limiter.release("u1")

    @pytest.mark.asyncio
    async def test_stats_reflect_state(self):
        limiter = LLMRateLimiter(max_concurrent=3, per_user_max=1)
        await limiter.acquire("u1")
        await limiter.acquire("u2")
        stats = limiter.stats()
        assert stats["available_slots"] == 1
        assert stats["active_users"] == 2

    @pytest.mark.asyncio
    async def test_waiting_estimate(self):
        limiter = LLMRateLimiter(max_concurrent=5, per_user_max=1)
        await limiter.acquire("u1")
        await limiter.acquire("u2")
        assert limiter.waiting <= 3


@pytest.fixture(autouse=True)
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
