"""Subagent handoff protocol tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.agent.handoff import HandoffManager
from tars.database import Database


class FakeChannel:
    def __init__(self):
        self.events = []

    async def send(self, session_id, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_handoff_manager_creates_pending_review_event():
    mgr = HandoffManager()
    handoff = mgr.create_pending(
        parent_session_id="sess-1",
        subagent_type="code",
        task_summary="write hello world",
        full_result="print('hello')",
    )
    payload = handoff.to_ws_payload()
    assert payload["status"] == "pending_review"
    assert payload["subagent_type"] == "code"
    assert payload["parent_session_id"] == "sess-1"
    assert "hello" in payload["result_preview"]


@pytest.mark.asyncio
async def test_accept_merges_result_into_session():
    from tars.agent.agent import AgentV2

    db = Database(":memory:")
    session = db.create_session(tenant_id="default")
    agent = AgentV2(db=db, provider=MagicMock())
    agent.current_model = "test-model"

    handoff = agent.handoff_manager.create_pending(
        parent_session_id=session.id,
        subagent_type="writing",
        task_summary="draft email",
        full_result="Dear team, ...",
    )
    channel = FakeChannel()

    ok = await agent.handle_subagent_handoff_action(
        handoff.id,
        "accept",
        channel=channel,
    )
    assert ok is True

    messages = db.get_messages(session.id)
    assert any("Dear team" in m.content for m in messages)

    handoff_events = [e for e in channel.events if e.get("type") == "subagent_handoff"]
    assert handoff_events
    assert handoff_events[-1]["status"] == "accepted"


@pytest.mark.asyncio
async def test_reject_does_not_merge_assistant_message():
    from tars.agent.agent import AgentV2

    db = Database(":memory:")
    session = db.create_session(tenant_id="default")
    agent = AgentV2(db=db, provider=MagicMock())

    handoff = agent.handoff_manager.create_pending(
        parent_session_id=session.id,
        subagent_type="code",
        task_summary="run tests",
        full_result="all passed",
    )
    channel = FakeChannel()

    ok = await agent.handle_subagent_handoff_action(
        handoff.id,
        "reject",
        channel=channel,
    )
    assert ok is True
    assert db.get_messages(session.id) == []

    rejected = [e for e in channel.events if e.get("type") == "subagent_handoff" and e.get("status") == "rejected"]
    assert rejected
