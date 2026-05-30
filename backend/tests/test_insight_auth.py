"""End-to-end auth tests for /api/insight after migration to require_module.

Verifies:
- 401 when X-API-Key is missing
- 401 when X-User-Role: admin is sent without a real admin api key
- 200 with a valid user api key
- Non-admin cannot access another user's datasource scope
"""
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


@pytest.fixture
def admin_key(app_client):
    _client, store = app_client
    for u in store.get_all_users():
        if u.role == UserRole.ADMIN:
            return u.api_key, u.id
    name = _unique("admin")
    user = store.create_user(username=name, email=f"{name}@test.local", role=UserRole.ADMIN)
    return user.api_key, user.id


def _skip_if_disabled(client):
    res = client.get("/api/insight/version", headers={"X-API-Key": "won't-match"})
    if res.status_code == 503 and "disabled" in res.text.lower():
        pytest.skip("insight module disabled in modules.yaml")


def test_insight_version_requires_api_key(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/insight/version")
    assert r.status_code == 401, r.text


def test_insight_version_with_admin_header_only_rejected(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/insight/version", headers={"X-User-Role": "admin"})
    assert r.status_code == 401, r.text


def test_insight_version_with_non_admin_user_role_admin_rejected(app_client, alice_key):
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = alice_key
    r = client.get(
        "/api/insight/version",
        headers={"X-API-Key": api_key, "X-User-Role": "admin"},
    )
    assert r.status_code == 403, r.text


def test_insight_version_standard_user_allowed(app_client, alice_key):
    """Standard role template includes insight module (see test_role_module_gating)."""
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = alice_key
    r = client.get(
        "/api/insight/version",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] == "INS-2.1.0"


def test_insight_version_with_admin_key_succeeds(app_client, admin_key):
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = admin_key
    r = client.get(
        "/api/insight/version",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "INS-2.1.0"


def test_insight_llm_settings_requires_auth(app_client):
    client, _ = app_client
    _skip_if_disabled(client)
    r = client.get("/api/insight/llm/settings")
    assert r.status_code == 401, r.text


def test_insight_brief_user_cannot_access_other_scope_datasource(app_client, alice_key):
    """Non-admin cannot read a datasource id that belongs to another user's scope."""
    client, _ = app_client
    _skip_if_disabled(client)
    api_key, _ = alice_key
    r = client.get(
        "/api/insight/datasources/some-other-tenant-ds-id/brief",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code in (403, 404), r.text
