import json

import pytest

from tars.channels.websocket import WebSocketChannel
from tars.tenant.context import TenantContext


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, event):
        self.sent.append(event)


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def handle_message(self, session_id, user_content, channel, file_ids=None, tenant_context=None, request_context=None):
        self.calls.append(
            {
                "session_id": session_id,
                "user_content": user_content,
                "tenant_id": tenant_context.tenant_id if tenant_context else None,
            }
        )


@pytest.mark.asyncio
async def test_websocket_channel_forwards_tenant_context():
    websocket = FakeWebSocket()
    tenant_context = TenantContext(tenant_id="tenant_ws", memory_manager=object())
    channel = WebSocketChannel(websocket, tenant_context=tenant_context)
    agent = FakeAgent()
    channel.set_agent(agent)

    await channel.handle_message(
        json.dumps(
            {
                "session_id": "sess-ws",
                "content": "hello",
            }
        )
    )

    assert agent.calls[0]["tenant_id"] == "tenant_ws"
    assert agent.calls[0]["session_id"] == "sess-ws"
