"""WebSocket message_feedback → FeedbackCollector."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.channels.websocket import WebSocketChannel
from tars.database import Database
from tars.evolution.manager import EvolutionManager


@pytest.mark.asyncio
async def test_websocket_message_feedback_records_event():
    db = Database(":memory:")
    mgr = EvolutionManager(db=db)
    agent = MagicMock()
    agent.evolution_manager = mgr

    ws = AsyncMock()
    channel = WebSocketChannel(ws, request_context={"user_id": "u1"})
    channel.set_agent(agent)

    payload = json.dumps({
        "type": "message_feedback",
        "session_id": "sess-1",
        "feedback": "down",
        "user_id": "u1",
    })
    await channel.handle_message(payload)

    rows = db.list_evolution_events(tenant_id="default", limit=1)
    assert rows
    assert rows[0]["signal"] == "thumbs_down"
    assert rows[0]["weight"] == 2.0
