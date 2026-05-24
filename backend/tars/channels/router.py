"""Route outbound channel events to registered adapters."""
from __future__ import annotations

from typing import Dict, Optional

from .adapter import ChannelAdapter


class ChannelRouter:
    """Register channel adapters and route outbound delivery."""

    def __init__(self):
        self._adapters: Dict[str, ChannelAdapter] = {}

    def register(self, channel_id: str, adapter: ChannelAdapter) -> None:
        self._adapters[channel_id] = adapter

    def get(self, channel_id: str) -> Optional[ChannelAdapter]:
        return self._adapters.get(channel_id)

    async def send(self, channel_id: str, session_id: str, event: dict) -> None:
        adapter = self._require(channel_id)
        await adapter.deliver_outbound(session_id, event)

    async def stream(self, channel_id: str, session_id: str, chunk: str) -> None:
        adapter = self._require(channel_id)
        await adapter.stream_outbound(session_id, chunk)

    def _require(self, channel_id: str) -> ChannelAdapter:
        adapter = self._adapters.get(channel_id)
        if adapter is None:
            raise KeyError(f"Channel adapter not registered: {channel_id}")
        return adapter
