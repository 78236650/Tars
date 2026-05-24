"""Follow-up queue tests."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.agent.follow_up_queue import FollowUpItem, FollowUpQueue
from tars.channels.websocket import WebSocketChannel


def test_follow_up_queue_try_acquire():
    queue = FollowUpQueue()
    assert queue.try_acquire("sess-1") is True
    assert queue.try_acquire("sess-1") is False
    queue.mark_idle("sess-1")
    assert queue.try_acquire("sess-1") is True


def test_follow_up_queue_fifo_and_busy_state():
    queue = FollowUpQueue()
    session_id = "sess-1"

    assert not queue.is_busy(session_id)
    queue.mark_busy(session_id)
    assert queue.is_busy(session_id)

    first = FollowUpItem("raw-1", session_id, "hello")
    second = FollowUpItem("raw-2", session_id, "world")

    assert queue.enqueue(first) == 1
    assert queue.enqueue(second) == 2
    assert queue.pending(session_id) == 2

    assert queue.pop(session_id) == first
    assert queue.pending(session_id) == 1
    assert queue.pop(session_id) == second
    assert queue.pop(session_id) is None

    queue.mark_idle(session_id)
    assert not queue.is_busy(session_id)


def test_follow_up_item_from_raw():
    raw = json.dumps({"session_id": "s1", "content": "ping", "file_ids": ["f1"]})
    data = json.loads(raw)
    item = FollowUpItem.from_raw(raw, data)
    assert item.session_id == "s1"
    assert item.content == "ping"
    assert item.file_ids == ["f1"]


@pytest.mark.asyncio
async def test_websocket_enqueues_while_busy_and_emits_queue_status():
    channel = WebSocketChannel(websocket=AsyncMock())
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = FollowUpQueue()
    channel.agent.follow_up_queue.try_acquire("sess-1")
    channel.agent.handle_message = AsyncMock()

    sent = []

    async def capture_send(session_id, event):
        sent.append(event)

    channel.send = capture_send

    raw = json.dumps({"session_id": "sess-1", "content": "queued message"})
    await channel.handle_message(raw)

    channel.agent.handle_message.assert_not_called()
    status_events = [e for e in sent if e.get("type") == "queue_status"]
    assert status_events
    assert status_events[0]["pending"] == 1
    assert status_events[0]["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_websocket_drains_queue_after_turn():
    channel = WebSocketChannel(websocket=AsyncMock())
    queue = FollowUpQueue()
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = queue

    handled = []

    async def fake_handle_message(**kwargs):
        handled.append(kwargs["user_content"])

    channel.agent.handle_message = fake_handle_message

    sent = []

    async def capture_send(session_id, event):
        sent.append(event)

    channel.send = capture_send

    queue.enqueue(FollowUpItem('{"session_id":"sess-1","content":"second"}', "sess-1", "second"))
    queue.enqueue(FollowUpItem('{"session_id":"sess-1","content":"third"}', "sess-1", "third"))

    raw = json.dumps({"session_id": "sess-1", "content": "first"})
    await channel.handle_message(raw)

    assert handled == ["first", "second", "third"]
    end_events = [e for e in sent if e.get("type") == "generation_end"]
    assert len(end_events) == 3
    final_status = [e for e in sent if e.get("type") == "queue_status"][-1]
    assert final_status["pending"] == 0


@pytest.mark.asyncio
async def test_router_reader_allows_enqueue_during_long_turn():
    from fastapi import WebSocketDisconnect

    from tars.agent.agent import AgentV2
    from tars.channels.router import ChannelRouter
    from tars.channels.websocket import ConnectionManager

    router = ChannelRouter()
    manager = ConnectionManager()
    agent = AgentV2(db=MagicMock(), provider=MagicMock())
    manager.set_agent(agent)

    websocket = AsyncMock()
    websocket.accept = AsyncMock()

    turn_started = asyncio.Event()
    release_turn = asyncio.Event()

    async def slow_handle_message(**kwargs):
        turn_started.set()
        await release_turn.wait()

    agent.handle_message = slow_handle_message

    messages = [
        json.dumps({"session_id": "sess-1", "content": "first"}),
        json.dumps({"session_id": "sess-1", "content": "second"}),
    ]
    receive_calls = {"count": 0}

    async def receive_side_effect():
        idx = receive_calls["count"]
        receive_calls["count"] += 1
        if idx < len(messages):
            return messages[idx]
        raise WebSocketDisconnect()

    websocket.receive_text = AsyncMock(side_effect=receive_side_effect)

    channel_events = []

    original_connect = manager.connect

    async def connect_and_capture(*args, **kwargs):
        channel = await original_connect(*args, **kwargs)

        async def capture_send(session_id, event):
            channel_events.append(event)

        channel.send = capture_send
        return channel

    manager.connect = connect_and_capture  # type: ignore[method-assign]

    run_task = asyncio.create_task(
        router.handle_websocket(
            websocket,
            connection_manager=manager,
            tenant_context=None,
            request_context={"transport": "websocket"},
        )
    )

    await asyncio.wait_for(turn_started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    release_turn.set()
    await asyncio.wait_for(run_task, timeout=2)

    queue_events = [e for e in channel_events if e.get("type") == "queue_status"]
    assert any(e.get("pending", 0) >= 1 for e in queue_events)


@pytest.mark.asyncio
async def test_follow_up_queue_no_concurrent_turns_during_drain():
    from tars.channels.websocket import WebSocketChannel

    channel = WebSocketChannel(websocket=AsyncMock())
    queue = FollowUpQueue()
    channel.agent = MagicMock()
    channel.agent.follow_up_queue = queue

    active = 0
    max_active = {"value": 0}
    call_count = {"value": 0}

    async def fake_handle_message(**kwargs):
        nonlocal active
        call_count["value"] += 1
        active += 1
        max_active["value"] = max(max_active["value"], active)
        await asyncio.sleep(0.05)
        active -= 1

    channel.agent.handle_message = fake_handle_message

    async def capture_send(session_id, event):
        return None

    channel.send = capture_send

    queue.enqueue(FollowUpItem('{"session_id":"sess-1","content":"queued"}', "sess-1", "queued"))

    raw = json.dumps({"session_id": "sess-1", "content": "first"})
    await channel.handle_message(raw)

    assert max_active["value"] == 1
    assert call_count["value"] == 2
