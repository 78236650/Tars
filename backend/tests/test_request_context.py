"""Request contextvars + UserContextMiddleware (TARS v5.0 Phase 1 Task 3)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

TEST_JWT_SECRET = "test-jwt-secret-for-request-context-tests"


@pytest.fixture(autouse=True)
def _jwt_secret_env(monkeypatch):
    monkeypatch.setenv("TARS_JWT_SECRET", TEST_JWT_SECRET)


def _build_store(tmp_path, monkeypatch, db_name="request-context.db"):
    from tars.database import Database, UserStore
    from tars.database.auth_token_store import AuthTokenStore
    import tars.main as main

    test_db = Database(db_path=str(tmp_path / db_name))
    test_store = UserStore(test_db)
    test_tokens = AuthTokenStore(test_db)
    monkeypatch.setattr(main, "user_store", test_store)
    monkeypatch.setattr(main, "auth_token_store", test_tokens)
    main.app.state.user_store = test_store
    main.app.state.auth_token_store = test_tokens
    return main, test_db, test_store, test_tokens


@pytest.fixture
def client(tmp_path, monkeypatch):
    main, test_db, test_store, _ = _build_store(tmp_path, monkeypatch)

    with TestClient(main.app) as http:
        yield http, test_store

    test_db.close()


def test_middleware_sets_context_with_bearer_token(client):
    from tars.context import current_user_id
    from tars.org import ORG_ID

    http, store = client
    user = store.create_user(
        username="ctxuser",
        email="ctx@example.com",
        password="CtxPass123!",
    )

    login = http.post(
        "/api/auth/login",
        json={"identifier": "ctx@example.com", "password": "CtxPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]

    assert current_user_id.get() is None

    response = http.get(
        "/api/users/me/context",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user.id
    assert body["org_id"] == ORG_ID
    assert current_user_id.get() is None


def test_context_cleared_after_request(client):
    from tars.context import current_org_id, current_user_id

    http, store = client
    user = store.create_user(
        username="cleared",
        email="cleared@example.com",
        password="ClearPass123!",
    )
    login = http.post(
        "/api/auth/login",
        json={"identifier": "cleared@example.com", "password": "ClearPass123!"},
    )
    token = login.json()["data"]["access_token"]

    http.get(
        "/api/users/me/context",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert current_user_id.get() is None
    assert current_org_id.get() is None

    http.get(
        "/api/users/me/context",
        headers={"X-API-Key": user.api_key},
    )
    assert current_user_id.get() is None
    assert current_org_id.get() is None


def test_dependency_returns_user_id_via_api_key(client):
    from tars.org import ORG_ID

    http, store = client
    user = store.create_user(
        username="apikeyctx",
        email="apikeyctx@example.com",
        password="ApiKeyPass123!",
    )

    response = http.get(
        "/api/users/me/context",
        headers={"X-API-Key": user.api_key},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": user.id, "org_id": ORG_ID}


def test_unauthenticated_context_endpoint_returns_401(client):
    http, _ = client
    response = http.get("/api/users/me/context")
    assert response.status_code == 401


def test_public_route_without_auth_headers(client):
    http, _ = client
    response = http.get("/api/modules")
    assert response.status_code == 200
