"""Stop generation control message tests."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.agent.follow_up_queue import FollowUpItem, FollowUpQueue
from tars.channels.websocket import WebSocketChannel


def test_follow_up_queue_cancel_and_clear_pending():
    queue = FollowUpQueue()
    session_id = "sess-1"

    queue.enqueue(FollowUpItem("raw", session_id, "queued"))
    assert queue.pending(session_id) == 1

    queue.request_cancel(session_id)
    assert queue.is_cancelled(session_id)

    cleared = queue.clear_pending(session_id)
    assert cleared == 1
    assert queue.pending(session_id) == 0

    queue.reset_cancel(session_id)
    assert not queue.is_cancelled(session_id)


@pytest.mark.asyncio
async def test_stop_generation_when_idle_clears_queue_and_emits_events():
    channel = WebSocketChannel(websocket=AsyncMock())
    queue = FollowUpQueue()
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = queue

    queue.enqueue(FollowUpItem('{"session_id":"sess-1","content":"later"}', "sess-1", "later"))

    sent = []

    async def capture_send(session_id, event):
        sent.append(event)

    channel.send = capture_send

    await channel.handle_message(json.dumps({"type": "stop_generation", "session_id": "sess-1"}))

    assert queue.pending("sess-1") == 0
    assert not queue.is_cancelled("sess-1")
    types = [e.get("type") for e in sent]
    assert "generation_stopped" in types
    assert "generation_end" in types
    assert "queue_status" in types
    assert sent[-2]["reason"] == "user_cancelled"


@pytest.mark.asyncio
async def test_stop_generation_cancels_active_turn():
    channel = WebSocketChannel(websocket=AsyncMock())
    queue = FollowUpQueue()
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = queue

    sent = []

    async def capture_send(session_id, event):
        sent.append(event)

    channel.send = capture_send

    turn_started = asyncio.Event()

    async def slow_handle_message(**kwargs):
        turn_started.set()
        session_id = kwargs["session_id"]
        ws_channel = kwargs["channel"]
        while not queue.is_cancelled(session_id):
            await asyncio.sleep(0.01)
        await ws_channel.send(session_id, {
            "type": "generation_stopped",
            "session_id": session_id,
            "reason": "user_cancelled",
            "timestamp": "2026-05-24T12:00:00+08:00",
        })

    channel.agent.handle_message = slow_handle_message

    turn_task = asyncio.create_task(
        channel.handle_message(json.dumps({"session_id": "sess-1", "content": "hello"}))
    )
    await asyncio.wait_for(turn_started.wait(), timeout=1)

    await channel.handle_message(json.dumps({"type": "stop_generation", "session_id": "sess-1"}))
    await asyncio.wait_for(turn_task, timeout=2)

    types = [e.get("type") for e in sent]
    assert types.count("generation_start") == 1
    assert "generation_stopped" in types
    assert types.count("generation_end") == 1
    assert not queue.is_busy("sess-1")


@pytest.mark.asyncio
async def test_stop_generation_skips_follow_up_drain():
    channel = WebSocketChannel(websocket=AsyncMock())
    queue = FollowUpQueue()
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = queue

    sent = []

    async def capture_send(session_id, event):
        sent.append(event)

    channel.send = capture_send

    handled = []

    async def fake_handle_message(**kwargs):
        handled.append(kwargs["user_content"])
        queue.request_cancel(kwargs["session_id"])

    channel.agent.handle_message = fake_handle_message
    queue.enqueue(FollowUpItem('{"session_id":"sess-1","content":"queued"}', "sess-1", "queued"))

    await channel.handle_message(json.dumps({"session_id": "sess-1", "content": "first"}))

    assert handled == ["first"]
    assert queue.pending("sess-1") == 0
