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
