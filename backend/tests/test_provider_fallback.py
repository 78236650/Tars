"""Provider fallback chain tests — v4.1.0"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from tars.models.base import ChatMessage, ChatResponse
from tars.models.fallback import (
    AllProvidersFailedError,
    chat_with_fallback,
    is_retryable,
    wrap_provider_with_fallback,
)


class FakeProvider:
    def __init__(self, name: str, fail: bool = False, retryable: bool = True):
        self.name = name
        self.model = f"{name}-model"
        self.fail = fail
        self.retryable = retryable
        self.calls = 0

    async def chat(self, messages, stream=False, model=None, **kwargs):
        self.calls += 1
        if self.fail:
            if self.retryable:
                raise ConnectionError("timeout connecting to provider")
            raise ValueError("bad request")
        return ChatResponse(content="ok", model=model or self.model, usage={"prompt_tokens": 1, "completion_tokens": 2})

    async def list_models(self):
        return [self.model]


@pytest.mark.asyncio
async def test_chat_with_fallback_disabled():
    primary = FakeProvider("primary")
    result = await chat_with_fallback(
        primary=primary,
        providers={"primary": primary},
        fallback_cfg={"enabled": False},
        messages=[ChatMessage(role="user", content="hi")],
    )
    assert result.content == "ok"
    assert primary.calls == 1


@pytest.mark.asyncio
async def test_chat_with_fallback_switches_on_retryable_error(tmp_path):
    db = __import__("tars.database", fromlist=["Database"]).Database(db_path=str(tmp_path / "fb.db"))
    primary = FakeProvider("p1", fail=True)
    backup = FakeProvider("p2")
    providers = {"p1": primary, "p2": backup}

    result = await chat_with_fallback(
        primary=primary,
        providers=providers,
        fallback_cfg={
            "enabled": True,
            "chain": [{"provider": "p2", "model": "p2-model"}],
            "retry_on": ["timeout"],
            "max_attempts": 3,
        },
        messages=[ChatMessage(role="user", content="hi")],
        primary_name="p1",
        db=db,
    )
    assert result.content == "ok"
    assert primary.calls == 1
    assert backup.calls == 1

    rows, total = db.list_provider_usage(provider="p2")
    assert total >= 1
    db.close()


@pytest.mark.asyncio
async def test_all_providers_fail():
    primary = FakeProvider("p1", fail=True)
    backup = FakeProvider("p2", fail=True)
    with pytest.raises(AllProvidersFailedError):
        await chat_with_fallback(
            primary=primary,
            providers={"p1": primary, "p2": backup},
            fallback_cfg={
                "enabled": True,
                "chain": [{"provider": "p2"}],
                "retry_on": ["timeout"],
                "max_attempts": 2,
            },
            messages=[ChatMessage(role="user", content="hi")],
            primary_name="p1",
        )


def test_is_retryable_timeout():
    assert is_retryable(ConnectionError("connection timeout")) is True
    assert is_retryable(ValueError("invalid json")) is False


def test_wrap_disabled_returns_primary():
    primary = FakeProvider("p1")
    wrapped = wrap_provider_with_fallback(primary, {}, {"enabled": False})
    assert wrapped is primary
