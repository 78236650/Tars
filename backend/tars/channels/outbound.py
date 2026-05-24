"""Unified WebSocket outbound delivery via ChannelRouter (F-12)."""
from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .router import ChannelRouter
    from .websocket import ConnectionManager


class OutboundDeliverer:
    """Prefer explicit ChannelRouter.send; fall back to ConnectionManager."""

    def __init__(
        self,
        *,
        channel_router: Optional["ChannelRouter"] = None,
        connection_manager: Optional["ConnectionManager"] = None,
        channel_id: str = "websocket",
    ):
        self.channel_router = channel_router
        self.connection_manager = connection_manager
        self.channel_id = channel_id

    async def send_personal(self, session_id: str, event: dict[str, Any]) -> bool:
        if not session_id:
            return False
        if self.channel_router is not None:
            try:
                await self.channel_router.send(self.channel_id, session_id, event)
                return True
            except KeyError:
                pass
        if self.connection_manager is not None:
            return await self.connection_manager.send_personal_message(session_id, event)
        return False

    async def broadcast(self, event: dict[str, Any]) -> None:
        if self.connection_manager is not None:
            await self.connection_manager.broadcast(event)
