"""Retry helper for transient LLM failures.

Used by InsightForge synthesizer to tolerate flaky API calls. Caller-side
exception filtering keeps unrelated bugs (auth, schema) from being masked.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable, TypeVar, Optional, Type, Tuple

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_call(
    callable_: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    backoff: float = 0.5,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    label: Optional[str] = None,
) -> T:
    last_exc: Optional[BaseException] = None
    for i in range(attempts):
        try:
            return await callable_()
        except retry_on as e:
            last_exc = e
            if i == attempts - 1:
                logger.warning(
                    "[retry_call] %s exhausted after %d attempts: %r",
                    label or "call",
                    attempts,
                    e,
                )
                raise
            wait = backoff * (2 ** i)
            logger.info(
                "[retry_call] %s attempt %d failed (%r); sleeping %.2fs",
                label or "call",
                i + 1,
                e,
                wait,
            )
            await asyncio.sleep(wait)
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_call: no attempts made")
