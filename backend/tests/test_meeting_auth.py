"""Meeting API auth: HTTP headers + WebSocket query api_key."""
import uuid

import pytest
from fastapi.testclient import TestClient

from tars.database.user_store import UserRole


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def app_client():
    from tars import main as tars_main
    from tars.api._auth import init_auth

    init_auth(tars_main.user_store, tars_main.auth_token_store)
    client = TestClient(tars_main.app)
    return client, tars_main.user_store


@pytest.fixture
def alice_key(app_client):
    _client, store = app_client
    name = _unique("alice")
    user = store.create_user(username=name, email=f"{name}@test.local", role=UserRole.USER)
    return user.api_key, user.id


def _skip_if_disabled(client):
    res = client.get("/api/meeting/history", headers={"X-API-Key": "invalid"})
    if res.status_code == 503 and "disabled" in res.text.lower():
        pytest.skip("meeting module disabled in modules.yaml")


def test_meeting_history_requires_api_key(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/meeting/history")
    assert r.status_code == 401, r.text


def test_meeting_history_with_user_key(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, user_id = alice_key
    r = client.get("/api/meeting/history", headers={"X-API-Key": api_key})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


def test_meeting_settings_requires_api_key(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/meeting/settings/templates")
    assert r.status_code == 401, r.text


def test_meeting_ws_requires_api_key(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/meeting/ws/record"):
            pass


def test_meeting_audio_not_found(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = alice_key
    r = client.get(
        "/api/meeting/00000000-0000-0000-0000-000000000099/audio",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404, r.text


def test_meeting_ws_with_api_key(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = alice_key
    with client.websocket_connect(f"/api/meeting/ws/record?api_key={api_key}") as ws:
        assert ws is not None
