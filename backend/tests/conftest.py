import pytest
import tempfile
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from tars.models.base import LLMProvider
from tars.database.base import Database


def setup_main_api_auth(db, *, role=None):
    """Wire UserStore + init_auth for main.app TestClient calls."""
    from tars.api._auth import init_auth
    from tars.database import UserStore
    from tars.gateway.permission import UserRole
    import tars.main as main

    store = UserStore(db)
    suffix = uuid.uuid4().hex[:8]
    user_role = role or UserRole.USER
    user = store.create_user(
        username=f"api_{suffix}",
        email=f"api_{suffix}@test.local",
        role=user_role,
    )
    main.user_store = store
    init_auth(store)
    return {"X-API-Key": user.api_key}, user


def setup_admin_auth(db):
    """Return (headers, admin user) for admin-only API routes."""
    from tars.gateway.permission import UserRole

    return setup_main_api_auth(db, role=UserRole.ADMIN)


def setup_knowledge_auth(db):
    """Wire auth store and return (headers, user) for mutating knowledge routes."""
    from tars.api._auth import init_auth
    from tars.database import UserStore
    from tars.gateway.permission import UserRole

    store = UserStore(db)
    suffix = uuid.uuid4().hex[:8]
    user = store.create_user(
        username=f"kb_{suffix}",
        email=f"kb_{suffix}@test.local",
        role=UserRole.USER,
    )
    init_auth(store)
    return {"X-API-Key": user.api_key}, user


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
