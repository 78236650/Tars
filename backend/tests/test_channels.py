# TARS Channels Layer Tests
# Phase 1 单元测试

import pytest
from tars.channels.base import ChannelMessage
from datetime import datetime


class TestChannelMessage:
    def test_create_with_defaults(self):
        """测试创建默认消息"""
        msg = ChannelMessage(
            channel="web", user_id="test", session_id="session1", content="test")
        
        assert msg.channel == "web"
        assert msg.user_id == "test"
        assert msg.session_id == "session1"
        assert msg.attachments == []
        assert isinstance(msg.timestamp, datetime)

    def test_create_with_all_fields(self):
        """测试创建完整消息"""
        attachments = [{"type": "image", "url": "test"}]
        ts = datetime(2024, 1, 1)
        msg = ChannelMessage(
            channel="web", user_id="test", session_id="session1", content="test",
            attachments=attachments, timestamp=ts)
        assert msg.attachments == attachments
        assert msg.timestamp == ts
