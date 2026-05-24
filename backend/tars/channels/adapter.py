"""Channel adapter protocol — outbound delivery for ChannelRouter."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChannelAdapter(Protocol):
    channel_id: str

    async def deliver_outbound(self, session_id: str, event: dict) -> None:
        """Deliver a structured outbound event to the client/session."""

    async def stream_outbound(self, session_id: str, chunk: str) -> None:
        """Deliver a streaming text chunk to the client/session."""


class ConnectionManagerOutboundAdapter:
    """Route outbound events through ConnectionManager session mapping."""

    channel_id = "websocket"

    def __init__(self, manager: Any):
        self._manager = manager

    async def deliver_outbound(self, session_id: str, event: dict) -> None:
        await self._manager.deliver_to_session(session_id, event)

    async def stream_outbound(self, session_id: str, chunk: str) -> None:
        from .websocket import now_iso

        await self.deliver_outbound(
            session_id,
            {
                "type": "text_chunk",
                "session_id": session_id,
                "content": chunk,
                "timestamp": now_iso(),
            },
        )


class ChannelInstanceAdapter:
    """Wrap an existing Channel implementation as a router adapter."""

    def __init__(self, channel_id: str, channel: Any):
        self.channel_id = channel_id
        self._channel = channel

    async def deliver_outbound(self, session_id: str, event: dict) -> None:
        await self._channel.send(session_id, event)

    async def stream_outbound(self, session_id: str, chunk: str) -> None:
        await self._channel.stream(session_id, chunk)
