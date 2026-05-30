"""JWT principal resolution via ``resolve_authenticated_principal`` (Task 4)."""

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from tars.api._auth import resolve_authenticated_principal
from tars.gateway.jwt_auth import create_access_token
from tars.org import ORG_ID

TEST_JWT_SECRET = "test-jwt-secret-for-auth-principal-tests"


@pytest.fixture(autouse=True)
def _jwt_secret_env(monkeypatch):
    monkeypatch.setenv("TARS_JWT_SECRET", TEST_JWT_SECRET)


class StubUser:
    def __init__(self, uid, role="user", role_template_id="standard", api_key=""):
        self.id = uid
        self.role = role
        self.role_template_id = role_template_id
        self.api_key = api_key


class StubStore:
    def __init__(self, api_key_map=None, users_by_id=None):
        self.api_key_map = api_key_map or {}
        self.users_by_id = users_by_id or {}

    def get_user_by_api_key(self, k):
        return self.api_key_map.get(k)

    def get_user_by_id(self, user_id):
        return self.users_by_id.get(user_id)


class StubTokenStore:
    def __init__(self, revoked=None):
        self.revoked = set(revoked or [])

    def is_token_revoked(self, jti):
        return jti in self.revoked


@pytest.fixture
def store():
    alice = StubUser("alice", api_key="key-alice")
    admin = StubUser("admin-1", role="admin", role_template_id="admin", api_key="key-admin")
    return StubStore(
        api_key_map={"key-alice": alice, "key-admin": admin},
        users_by_id={"alice": alice, "admin-1": admin},
    )


@pytest.fixture
def token_store():
    return StubTokenStore()


def test_principal_from_valid_jwt(store, token_store):
    token = create_access_token("alice")
    auth_header = f"Bearer {token}"

    p = resolve_authenticated_principal(
        api_key=None,
        role_header=None,
        tenant_header=None,
        user_store=store,
        authorization=auth_header,
        auth_token_store=token_store,
    )

    assert p.user_id == "alice"
    assert p.tenant_id == ORG_ID
    assert p.api_key == "key-alice"
    assert not p.is_admin


def test_revoked_jti_returns_401(store, token_store):
    token = create_access_token("alice")
    from tars.gateway.jwt_auth import decode_access_token

    jti = decode_access_token(token)["jti"]
    token_store.revoked.add(jti)

    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key=None,
            role_header=None,
            tenant_header=None,
            user_store=store,
            authorization=f"Bearer {token}",
            auth_token_store=token_store,
        )
    assert exc.value.status_code == 401


def test_expired_jwt_returns_401(store, token_store):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": "alice",
            "org_id": ORG_ID,
            "exp": past,
            "jti": "expired-jti",
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key=None,
            role_header=None,
            tenant_header=None,
            user_store=store,
            authorization=f"Bearer {token}",
            auth_token_store=token_store,
        )
    assert exc.value.status_code == 401


def test_api_key_still_works(store, token_store):
    p = resolve_authenticated_principal(
        api_key="key-alice",
        role_header=None,
        tenant_header=None,
        user_store=store,
        authorization=None,
        auth_token_store=token_store,
    )
    assert p.user_id == "alice"
    assert p.api_key == "key-alice"


def test_invalid_bearer_does_not_fall_through_to_api_key(store, token_store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key="key-alice",
            role_header=None,
            tenant_header=None,
            user_store=store,
            authorization="Bearer not-a-valid-jwt",
            auth_token_store=token_store,
        )
    assert exc.value.status_code == 401


def test_neither_bearer_nor_api_key_returns_401(store, token_store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key=None,
            role_header=None,
            tenant_header=None,
            user_store=store,
            authorization=None,
            auth_token_store=token_store,
        )
    assert exc.value.status_code == 401
