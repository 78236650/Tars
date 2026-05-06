import pytest
from tars.models.base import ChatMessage, ModelResponse, LLMProvider


class TestChatMessage:
    def test_create_basic_message(self):
        msg = ChatMessage(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_call_id is None
        assert msg.name is None

    def test_create_message_with_tool_call(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_call_id="call_123",
            name="search"
        )
        
        assert msg.role == "assistant"
        assert msg.content == ""
        assert msg.tool_call_id == "call_123"
        assert msg.name == "search"


class TestModelResponse:
    def test_create_response(self):
        response = ModelResponse(content="Response text", model="gpt-4o")
        
        assert response.content == "Response text"
        assert response.model == "gpt-4o"
        assert response.usage is None

    def test_create_response_with_usage(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        response = ModelResponse(
            content="Response",
            model="claude-sonnet-4",
            usage=usage
        )
        
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["total_tokens"] == 150


class TestLLMProvider:
    def test_provider_is_abstract(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_concrete_provider(self):
        class ConcreteProvider(LLMProvider):
            async def chat(self, messages, stream=False, model=None, temperature=0.7, max_tokens=None):
                return ModelResponse(content="Mock response", model="test-model")
        
        provider = ConcreteProvider()
        assert isinstance(provider, LLMProvider)
