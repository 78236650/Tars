"""Tests for TARS ProviderBase — Phase 3 Task 1."""
import pytest
from tars.models.base import ProviderBase, ChatResponse, ModelInfo, ChatMessage, LLMProvider


class TestProviderBase:
    """Verify abstract provider interface."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ProviderBase()

    def test_chat_response_dataclass(self):
        r = ChatResponse(content="hello", model="qwen3")
        assert r.content == "hello"
        assert r.tool_calls is None
        assert r.usage is None

    def test_chat_response_with_tools(self):
        r = ChatResponse(
            content="",
            tool_calls=[{"name": "weather", "arguments": {}}],
            model="qwen3",
        )
        assert len(r.tool_calls) == 1

    def test_model_info_dataclass(self):
        m = ModelInfo(id="qwen3:8b", name="Qwen3 8B", supports_tools=True, context_length=32768)
        assert m.supports_tools is True
        assert m.supports_vision is False
        assert m.context_length == 32768

    def test_concrete_provider_can_be_created(self):
        """A properly implemented provider should be instantiable."""
        class MyProvider(ProviderBase):
            name = "test"
            display_name = "Test"

            async def chat(self, **kwargs):
                return ChatResponse(content="ok", model="test")

            async def list_models(self):
                return ["test-model"]

        p = MyProvider()
        assert p.name == "test"
        assert p.supports_tools is False

    def test_llm_provider_alias(self):
        """LLMProvider should be the same as ProviderBase."""
        assert LLMProvider is ProviderBase
