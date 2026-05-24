import pytest

from tars.channels.websocket import ConnectionManager


class FakeChannel:
    def __init__(self):
        self.events = []

    async def send(self, session_id, event):
        self.events.append(event)

    async def _send_direct(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_connection_manager_can_route_by_session_id():
    manager = ConnectionManager()
    channel = FakeChannel()

    manager.active_connections["conn-a"] = channel
    manager.bind_session("session-a", "conn-a")
    await manager.send_personal_message("session-a", {"type": "cron_reminder"})

    assert channel.events == [{"type": "cron_reminder"}]


@pytest.mark.asyncio
async def test_connection_manager_routes_outbound_via_channel_router():
    from tars.channels.adapter import ConnectionManagerOutboundAdapter
    from tars.channels.router import ChannelRouter

    manager = ConnectionManager()
    router = ChannelRouter()
    router.register("websocket", ConnectionManagerOutboundAdapter(manager))
    manager.configure_router(router, use_router=True)

    channel = FakeChannel()
    manager.active_connections["conn-a"] = channel
    manager.bind_session("session-a", "conn-a")

    await manager.send_personal_message("session-a", {"type": "cron_reminder"})

    assert channel.events == [{"type": "cron_reminder"}]
