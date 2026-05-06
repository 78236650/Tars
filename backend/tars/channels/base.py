# TARS Channels Layer - Base Abstract Class
# Layer 1: 通道层抽象

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta


@dataclass
class ChannelMessage:
    """标准化的通道消息"""
    channel: str
    user_id: str
    session_id: str
    content: str
    attachments: list = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone(timedelta(hours=8)))
        if self.attachments is None:
            self.attachments = []


class Channel(ABC):
    """通道抽象基类"""

    @abstractmethod
    async def receive(self, raw_message: Any) -> ChannelMessage:
        """将原始消息标准化为 ChannelMessage"""
        pass

    @abstractmethod
    async def send(self, session_id: str, event: dict) -> None:
        """发送事件到客户端"""
        pass

    @abstractmethod
    async def stream(self, session_id: str, chunk: str) -> None:
        """流式推送文本片段"""
        pass
