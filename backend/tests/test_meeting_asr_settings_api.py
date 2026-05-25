"""Meeting ASR settings API tests."""
import uuid

import pytest
from fastapi.testclient import TestClient

from tars.database.user_store import UserRole
from tars.meeting.config import _load_meeting_asr_config_base, load_meeting_asr_config, set_meeting_asr_runtime


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def app_client():
    from tars import main as tars_main

    return TestClient(tars_main.app), tars_main.user_store


@pytest.fixture
def alice_key(app_client):
    _client, store = app_client
    name = _unique("alice")
    user = store.create_user(username=name, email=f"{name}@test.local", role=UserRole.USER)
    return user.api_key


@pytest.fixture(autouse=True)
def reset_asr_runtime():
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)
    yield
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)


def _skip_if_disabled(client):
    res = client.get("/api/meeting/history", headers={"X-API-Key": "invalid"})
    if res.status_code == 503 and "disabled" in res.text.lower():
        pytest.skip("meeting module disabled in modules.yaml")


def test_get_asr_settings_includes_whisper_options(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/meeting/settings/asr", headers={"X-API-Key": alice_key})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["whisper_model"] == "small"
    assert len(data["whisper_model_options"]) >= 5
    assert any(opt["id"] == "medium" for opt in data["whisper_model_options"])


def test_set_asr_whisper_model(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.put(
        "/api/meeting/settings/asr",
        headers={"X-API-Key": alice_key},
        json={"whisper_model": "medium"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["whisper_model"] == "medium"
    assert load_meeting_asr_config()["model"] == "medium"


def test_set_asr_whisper_model_rejects_invalid(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.put(
        "/api/meeting/settings/asr",
        headers={"X-API-Key": alice_key},
        json={"whisper_model": "huge"},
    )
    assert r.status_code == 400, r.text
