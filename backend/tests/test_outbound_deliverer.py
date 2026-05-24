"""OutboundDeliverer routes via ChannelRouter when configured."""
import pytest

from tars.channels.outbound import OutboundDeliverer
from tars.channels.router import ChannelRouter


class FakeAdapter:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def deliver_outbound(self, session_id: str, event: dict) -> None:
        self.events.append((session_id, event))

    async def stream_outbound(self, session_id: str, chunk: str) -> None:
        pass


class FakeConnectionManager:
    def __init__(self):
        self.personal: list[tuple[str, dict]] = []

    async def send_personal_message(self, session_id, event):
        self.personal.append((session_id, event))
        return True

    async def broadcast(self, event):
        pass


@pytest.mark.asyncio
async def test_outbound_prefers_channel_router():
    router = ChannelRouter()
    adapter = FakeAdapter()
    router.register("websocket", adapter)
    cm = FakeConnectionManager()
    deliverer = OutboundDeliverer(channel_router=router, connection_manager=cm)

    ok = await deliverer.send_personal("sess-1", {"type": "ping"})
    assert ok is True
    assert adapter.events == [("sess-1", {"type": "ping"})]
    assert cm.personal == []


@pytest.mark.asyncio
async def test_outbound_falls_back_to_connection_manager():
    cm = FakeConnectionManager()
    deliverer = OutboundDeliverer(connection_manager=cm)

    ok = await deliverer.send_personal("sess-2", {"type": "pong"})
    assert ok is True
    assert cm.personal == [("sess-2", {"type": "pong"})]
