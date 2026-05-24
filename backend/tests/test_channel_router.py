"""ChannelRouter and registry tests."""
from unittest.mock import AsyncMock

import pytest

from tars.channels.registry import ChannelRegistry
from tars.channels.router import ChannelRouter


@pytest.mark.asyncio
async def test_router_send_routes_to_registered_channel():
    router = ChannelRouter()
    mock = AsyncMock()
    mock.channel_id = "websocket"
    router.register("websocket", mock)
    await router.send("websocket", "sess-1", {"type": "token", "content": "hi"})
    mock.deliver_outbound.assert_called_once_with("sess-1", {"type": "token", "content": "hi"})


@pytest.mark.asyncio
async def test_router_stream_routes_to_registered_channel():
    router = ChannelRouter()
    mock = AsyncMock()
    mock.channel_id = "websocket"
    router.register("websocket", mock)
    await router.stream("websocket", "sess-1", "chunk")
    mock.stream_outbound.assert_called_once_with("sess-1", "chunk")


@pytest.mark.asyncio
async def test_router_send_unknown_channel_raises():
    router = ChannelRouter()
    with pytest.raises(KeyError, match="not registered"):
        await router.send("missing", "sess-1", {"type": "token"})


def test_registry_loads_channels_yaml(tmp_path):
    cfg = tmp_path / "channels.yaml"
    cfg.write_text(
        "channels:\n  use_router: true\n  adapters:\n    websocket:\n      enabled: true\n",
        encoding="utf-8",
    )
    reg = ChannelRegistry.load(cfg)
    assert reg.use_router is True
    assert reg.is_adapter_enabled("websocket") is True


@pytest.mark.asyncio
async def test_handle_websocket_runs_message_loop_and_disconnects():
    from unittest.mock import AsyncMock, MagicMock

    from tars.channels.router import ChannelRouter
    from tars.channels.websocket import ConnectionManager, WebSocketChannel

    router = ChannelRouter()
    manager = ConnectionManager()
    agent = MagicMock()
    manager.set_agent(agent)

    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.receive_text = AsyncMock(
        side_effect=[
            '{"session_id":"s1","content":"hi"}',
            __import__("fastapi").WebSocketDisconnect(),
        ]
    )

    handled = []

    async def fake_handle_message(raw):
        handled.append(raw)

    original_connect = manager.connect

    async def connect_and_patch(*args, **kwargs):
        channel = await original_connect(*args, **kwargs)
        channel.handle_message = fake_handle_message
        return channel

    manager.connect = connect_and_patch  # type: ignore[method-assign]

    await router.handle_websocket(
        websocket,
        connection_manager=manager,
        tenant_context=None,
        request_context={"transport": "websocket"},
    )

    assert handled
    assert not manager.active_connections
