"""Tests for the centralized authentication helper (`tars.api._auth`).

These tests assert the contract for `resolve_authenticated_principal`:

- An empty `X-API-Key` is rejected with 401.
- An invalid `X-API-Key` is rejected with 401.
- `X-User-Role: admin` requires the api key to belong to a real admin user.
- `X-Tenant-Id` is honoured for admins (impersonation), ignored for others.
"""
import pytest
from fastapi import HTTPException

from tars.api._auth import resolve_authenticated_principal


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
    assert p.tenant_id == "anybody"  # admin can impersonate via header


def test_non_admin_tenant_header_ignored(store):
    p = resolve_authenticated_principal(
        api_key="key-alice", role_header=None, tenant_header="someone-else", user_store=store
    )
    assert not p.is_admin
    assert p.tenant_id == "alice"  # X-Tenant-Id is ignored for non-admins


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
    assert p.tenant_id == "admin-1"


def test_user_store_uninitialized_returns_503(store):
    with pytest.raises(HTTPException) as exc:
        resolve_authenticated_principal(
            api_key="key-alice", role_header=None, tenant_header=None, user_store=None
        )
    assert exc.value.status_code == 503
