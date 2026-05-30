"""Tests for the centralized authentication helper (`tars.api._auth`).

These tests assert the contract for `resolve_authenticated_principal`:

- Missing Bearer and `X-API-Key` -> 401.
- An invalid `X-API-Key` is rejected with 401.
- `X-User-Role: admin` requires the api key to belong to a real admin user.
- `X-Tenant-Id` is ignored (v5.0 single org); `tenant_id` is always `org_default`.
- JWT Bearer auth is covered in ``test_auth_jwt_principal.py``.
"""
import pytest
from fastapi import HTTPException

from tars.gateway.permission import UserRole

from tars.api._auth import resolve_authenticated_principal
from tars.org import ORG_ID


class StubUser:
    def __init__(self, uid, role="user", role_template_id="standard"):
        self.id = uid
        self.role = role
        self.role_template_id = role_template_id


class StubStore:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_user_by_api_key(self, k):
        return self.mapping.get(k)


@pytest.fixture
def store():
    return StubStore({
        "key-alice": StubUser("alice"),
        "key-admin": StubUser("admin-1", role="admin", role_template_id="admin"),
    })


def test_no_api_key_no_admin_header_raises(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key=None, role_header=None, tenant_header=None, user_store=store
        )
    assert exc.value.status_code == 401


def test_admin_header_without_api_key_rejected(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key=None, role_header="admin", tenant_header=None, user_store=store
        )
    assert exc.value.status_code == 401


def test_admin_header_with_non_admin_key_rejected(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key="key-alice", role_header="admin", tenant_header=None, user_store=store
        )
    assert exc.value.status_code == 403


def test_admin_header_with_admin_key_accepted(store):
    p = resolve_authenticated_principal(
        api_key="key-admin", role_header="admin", tenant_header="anybody", user_store=store
    )
    assert p.is_admin
    assert p.tenant_id == ORG_ID


def test_non_admin_tenant_header_ignored(store):
    p = resolve_authenticated_principal(
        api_key="key-alice", role_header=None, tenant_header="someone-else", user_store=store
    )
    assert not p.is_admin
    assert p.tenant_id == ORG_ID


def test_unknown_api_key_rejected(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key="deadbeef", role_header=None, tenant_header=None, user_store=store
        )
    assert exc.value.status_code == 401


def test_admin_without_tenant_header_uses_self(store):
    p = resolve_authenticated_principal(
        api_key="key-admin", role_header=None, tenant_header=None, user_store=store
    )
    assert p.is_admin
    assert p.tenant_id == ORG_ID


def test_user_store_uninitialized_returns_503(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key="key-alice", role_header=None, tenant_header=None, user_store=None
        )
    assert exc.value.status_code == 503


def test_admin_role_enum_accepted_with_admin_header():
    """UserStore returns UserRole enum — must not 403 when frontend sends X-User-Role: admin."""
    enum_store = StubStore({
        "key-admin-enum": StubUser("admin-enum", role=UserRole.ADMIN, role_template_id="admin"),
    })
    p = resolve_authenticated_principal(
        api_key="key-admin-enum",
        role_header="admin",
        tenant_header="tenant-x",
        user_store=enum_store,
    )
    assert p.is_admin
    assert p.role == "admin"
    assert p.tenant_id == ORG_ID
