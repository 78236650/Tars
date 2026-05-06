import pytest
from tars.channels.base import ChannelMessage, Channel
from datetime import datetime


class TestChannelMessage:
    def test_create_with_defaults(self):
        msg = ChannelMessage(
            channel="web", user_id="test_user", session_id="session1", content="hello")
        
        assert msg.channel == "web"
        assert msg.user_id == "test_user"
        assert msg.session_id == "session1"
        assert msg.content == "hello"
        assert msg.attachments == []
        assert isinstance(msg.timestamp, datetime)

    def test_create_with_all_fields(self):
        attachments = [{"type": "image", "url": "http://test.com/img.png"}]
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = ChannelMessage(
            channel="telegram",
            user_id="user123",
            session_id="session_abc",
            content="test message",
            attachments=attachments,
            timestamp=ts
        )
        
        assert msg.channel == "telegram"
        assert msg.user_id == "user123"
        assert msg.session_id == "session_abc"
        assert msg.content == "test message"
        assert msg.attachments == attachments
        assert msg.timestamp == ts

    def test_attachments_default_empty_list(self):
        msg = ChannelMessage(channel="web", user_id="test", session_id="s1", content="test")
        assert msg.attachments == []
        msg.attachments.append({"type": "file"})
        msg2 = ChannelMessage(channel="web", user_id="test", session_id="s2", content="test")
        assert msg2.attachments == []

    def test_timestamp_default_utcnow(self):
        msg = ChannelMessage(channel="web", user_id="test", session_id="s1", content="test")
        assert msg.timestamp is not None
        assert (datetime.utcnow() - msg.timestamp).total_seconds() < 1


class TestChannelAbstract:
    def test_channel_is_abstract(self):
        with pytest.raises(TypeError):
            Channel()

    def test_channel_requires_abstract_methods(self):
        class ConcreteChannel(Channel):
            async def receive(self, raw_message):
                pass
            async def send(self, session_id, event):
                pass
            async def stream(self, session_id, chunk):
                pass
        
        channel = ConcreteChannel()
        assert isinstance(channel, Channel)
