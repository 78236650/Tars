"""Route outbound channel events to registered adapters."""
from __future__ import annotations

import traceback
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .adapter import ChannelAdapter

if TYPE_CHECKING:
    from .websocket import ConnectionManager


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

    async def handle_websocket(
        self,
        websocket: WebSocket,
        *,
        connection_manager: "ConnectionManager",
        tenant_context: Any = None,
        request_context: dict | None = None,
    ) -> None:
        """Accept a WebSocket, run the inbound message loop, and clean up on disconnect."""
        connection_id = str(uuid.uuid4())
        channel = await connection_manager.connect(
            connection_id,
            websocket,
            tenant_context=tenant_context,
            request_context=request_context,
        )
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    await channel.handle_message(data)
                except Exception as e:
                    print(f"[ChannelRouter] 连接 {connection_id[:8]}… 处理异常: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    connection_manager.disconnect(connection_id)
                    break
        except WebSocketDisconnect:
            connection_manager.disconnect(connection_id)

    def _require(self, channel_id: str) -> ChannelAdapter:
        adapter = self._adapters.get(channel_id)
        if adapter is None:
            raise KeyError(f"Channel adapter not registered: {channel_id}")
        return adapter
