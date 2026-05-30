"""WebSocket JWT / API key authentication (v5.0 T1.5)."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from tars.api._auth import init_auth
from tars.gateway.jwt_auth import create_access_token
from tars.gateway.ws_auth import authenticate_websocket, resolve_websocket_principal
from tars.org import ORG_ID

TEST_JWT_SECRET = "test-jwt-secret-ws-auth"


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("TARS_JWT_SECRET", TEST_JWT_SECRET)


class StubUser:
    def __init__(self, uid, role="user", api_key=""):
        self.id = uid
        self.role = role
        self.role_template_id = "standard"
        self.api_key = api_key


class StubStore:
    def __init__(self):
        alice = StubUser("alice", api_key="key-alice")
        self.users = {"alice": alice}
        self.keys = {"key-alice": alice}

    def get_user_by_api_key(self, k):
        return self.keys.get(k)

    def get_user_by_id(self, user_id):
        return self.users.get(user_id)


class StubTokenStore:
    def __init__(self, revoked=None):
        self.revoked = set(revoked or [])

    def is_token_revoked(self, jti):
        return jti in self.revoked


def _ws(query: str = "", headers: dict | None = None):
    ws = MagicMock()
    params = {}
    for part in query.lstrip("?").split("&"):
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        from urllib.parse import unquote

        params[k] = unquote(v)
    ws.query_params = MagicMock()
    ws.query_params.get = lambda k, default="": params.get(k, default)
    ws.headers = MagicMock()
    ws.headers.get = lambda k, default="": (headers or {}).get(k.lower(), default)
    return ws


@pytest.fixture
def store():
    s = StubStore()
    init_auth(s, StubTokenStore())
    return s


def test_resolve_websocket_principal_from_token(store):
    token = create_access_token("alice")
    ws = _ws(f"token={token}")
    p = resolve_websocket_principal(ws, user_store=store, auth_token_store=StubTokenStore())
    assert p.user_id == "alice"
    assert p.tenant_id == ORG_ID


def test_resolve_websocket_principal_from_api_key(store):
    ws = _ws("api_key=key-alice")
    p = resolve_websocket_principal(ws, user_store=store)
    assert p.user_id == "alice"


def test_resolve_websocket_principal_rejects_bad_token(store):
    ws = _ws("token=not-a-jwt")
    with pytest.raises(HTTPException) as exc:
        resolve_websocket_principal(ws, user_store=store)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_websocket_closes_without_credentials(store):
    ws = _ws()
    ws.close = AsyncMock()
    result = await authenticate_websocket(ws, user_store=store, require_auth=True)
    assert result is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_sets_context(store):
    from tars.context import clear_request_context, get_current_user_id

    token = create_access_token("alice")
    ws = _ws(f"token={token}")
    ws.close = AsyncMock()
    try:
        p = await authenticate_websocket(
            ws, user_store=store, auth_token_store=StubTokenStore()
        )
        assert p is not None
        assert get_current_user_id() == "alice"
    finally:
        clear_request_context()
