import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from tars.models.base import LLMProvider
from tars.database.base import Database


class MockLLMProvider(LLMProvider):
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return {"content": "Mock response", "tool_calls": None}

    async def stream(self, messages, **kwargs):
        self.call_count += 1
        if self.responses:
            response = self.responses.pop(0)
            for chunk in response.get("content", "Mock response"):
                yield {"type": "text_chunk", "content": chunk}
            yield {"type": "done"}
        else:
            for chunk in "Mock response":
                yield {"type": "text_chunk", "content": chunk}
            yield {"type": "done"}

    def get_schema(self):
        return []


@pytest.fixture
def mock_llm_provider():
    return MockLLMProvider()


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db():
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def mock_auth_manager():
    mock = MagicMock()
    mock.verify_api_key.return_value = True
    mock.get_user_id.return_value = "test_user"
    return mock


@pytest.fixture
def mock_rate_limiter():
    mock = MagicMock()
    mock.check.return_value = True
    return mock


@pytest.fixture
def mock_security_policy():
    mock = MagicMock()
    mock.validate_path.return_value = True
    mock.is_dangerous_command.return_value = False
    return mock


@pytest.fixture
def mock_gateway(mock_auth_manager, mock_rate_limiter, mock_security_policy):
    mock = MagicMock()
    mock.auth = mock_auth_manager
    mock.rate_limiter = mock_rate_limiter
    mock.security = mock_security_policy
    return mock
