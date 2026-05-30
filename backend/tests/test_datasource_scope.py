"""v5.0 datasource_scope_id helper."""

import pytest
from fastapi import HTTPException

from tars.api._auth import Principal
from tars.api.scope import datasource_scope_id, org_scope
from tars.org import ORG_ID


def test_org_scope():
    p = Principal(
        user_id="u1",
        role="user",
        role_template_id="standard",
        tenant_id=ORG_ID,
        is_admin=False,
        api_key="k",
    )
    assert org_scope(p) == ORG_ID


def test_datasource_scope_uses_user_id():
    p = Principal(
        user_id="alice",
        role="user",
        role_template_id="standard",
        tenant_id=ORG_ID,
        is_admin=False,
        api_key="k",
    )
    assert datasource_scope_id(p) == "alice"


def test_datasource_scope_admin_override():
    p = Principal(
        user_id="admin-1",
        role="admin",
        role_template_id="admin",
        tenant_id=ORG_ID,
        is_admin=True,
        api_key="k",
    )
    assert datasource_scope_id(p, user_id="bob") == "bob"


def test_datasource_scope_non_admin_override_forbidden():
    p = Principal(
        user_id="alice",
        role="user",
        role_template_id="standard",
        tenant_id=ORG_ID,
        is_admin=False,
        api_key="k",
    )
    with pytest.raises(HTTPException) as exc:
        datasource_scope_id(p, user_id="bob")
    assert exc.value.status_code == 403
