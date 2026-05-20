"""SSE workflow events must not block asyncio event loop (P0 #2)."""
import asyncio
import time

import pytest

from tars.insight.workflow_events import acquire_connection, aiter_sse, publish, release_connection


@pytest.mark.asyncio
async def test_aiter_sse_uses_async_sleep_not_blocking():
    assert acquire_connection()
    run_id = "test-run-sse"
    publish(run_id, "progress", {"percent": 1})

    async def drain_one_chunk():
        agen = aiter_sse(run_id, poll_interval_sec=0.05)
        chunk = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
        await agen.aclose()
        return chunk

    loop = asyncio.get_running_loop()
    start = loop.time()
    concurrent = asyncio.create_task(asyncio.sleep(0.02))
    chunk = await drain_one_chunk()
    await concurrent
    elapsed = loop.time() - start

    assert "progress" in chunk
    assert elapsed < 0.5, "aiter_sse should yield quickly without blocking the loop"
    release_connection()
