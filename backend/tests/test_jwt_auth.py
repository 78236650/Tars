"""JWT issuance/validation tests (TARS v5.0 Phase 1 Task 2).

Tests set ``TARS_JWT_SECRET`` explicitly. Production must set the same env var;
the module's dev-only fallback is not used when this fixture runs.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

TEST_JWT_SECRET = "test-jwt-secret-for-pytest-only-do-not-use-in-prod"


@pytest.fixture(autouse=True)
def _jwt_secret_env(monkeypatch):
    monkeypatch.setenv("TARS_JWT_SECRET", TEST_JWT_SECRET)


def _build_store(tmp_path, monkeypatch, db_name="jwt-auth.db"):
    from tars.database import Database, UserStore
    from tars.database.auth_token_store import AuthTokenStore
    import tars.main as main

    test_db = Database(db_path=str(tmp_path / db_name))
    test_store = UserStore(test_db)
    test_tokens = AuthTokenStore(test_db)
    monkeypatch.setattr(main, "user_store", test_store)
    monkeypatch.setattr(main, "auth_token_store", test_tokens)
    return main, test_db, test_store, test_tokens


@pytest.fixture
def client(tmp_path, monkeypatch):
    main, test_db, test_store, _ = _build_store(tmp_path, monkeypatch)

    with TestClient(main.app) as test_client:
        yield test_client, test_store

    test_db.close()


def test_create_decode_roundtrip():
    from tars.gateway.jwt_auth import create_access_token, decode_access_token
    from tars.org import ORG_ID

    token = create_access_token("user-abc")
    claims = decode_access_token(token)

    assert claims["sub"] == "user-abc"
    assert claims["org_id"] == ORG_ID
    assert claims["jti"]
    assert claims["exp"]


def test_expired_token_fails():
    from tars.gateway.jwt_auth import decode_access_token
    from tars.org import ORG_ID

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": "user-x", "org_id": ORG_ID, "exp": past, "jti": "expired-jti"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_wrong_secret_fails():
    from tars.gateway.jwt_auth import decode_access_token
    from tars.org import ORG_ID

    token = jwt.encode(
        {
            "sub": "user-x",
            "org_id": ORG_ID,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "jti": "wrong-secret-jti",
        },
        "not-the-test-secret",
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_login_returns_access_token(client):
    http, store = client
    user = store.create_user(
        username="jwtuser",
        email="jwt@example.com",
        password="JwtPass123!",
    )

    response = http.post(
        "/api/auth/login",
        json={"identifier": "jwt@example.com", "password": "JwtPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["api_key"] == user.api_key
    assert data["data"]["access_token"]

    from tars.gateway.jwt_auth import decode_access_token

    claims = decode_access_token(data["data"]["access_token"])
    assert claims["sub"] == user.id


def test_login_registers_jti_in_auth_tokens(tmp_path, monkeypatch):
    from tars.gateway.jwt_auth import decode_access_token

    main, test_db, store, token_store = _build_store(tmp_path, monkeypatch, "jwt-jti.db")
    try:
        user = store.create_user(
            username="jwtuser2",
            email="jwt2@example.com",
            password="JwtPass123!",
        )
        with TestClient(main.app) as http:
            response = http.post(
                "/api/auth/login",
                json={"identifier": "jwt2@example.com", "password": "JwtPass123!"},
            )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        claims = decode_access_token(token)
        assert not token_store.is_token_revoked(claims["jti"])
    finally:
        test_db.close()
