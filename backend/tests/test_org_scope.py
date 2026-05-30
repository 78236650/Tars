"""v5.0 org scope: all principals share ORG_ID, users differ by user_id."""
from tars.api._auth import resolve_authenticated_principal
from tars.org import ORG_ID


class StubUser:
    def __init__(self, uid, role="user"):
        self.id = uid
        self.role = role
        self.role_template_id = "standard"


class StubStore:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_user_by_api_key(self, k):
        return self.mapping.get(k)


def test_two_users_same_org_scope():
    store = StubStore({
        "k-a": StubUser("user-a"),
        "k-b": StubUser("user-b"),
    })
    pa = resolve_authenticated_principal("k-a", None, None, store)
    pb = resolve_authenticated_principal("k-b", None, None, store)
    assert pa.user_id == "user-a"
    assert pb.user_id == "user-b"
    assert pa.tenant_id == ORG_ID
    assert pb.tenant_id == ORG_ID
    assert pa.tenant_id == pb.tenant_id


def test_non_admin_tenant_header_does_not_change_org():
    store = StubStore({"k-a": StubUser("user-a")})
    p = resolve_authenticated_principal(
        "k-a", None, "someone-else", store
    )
    assert p.tenant_id == ORG_ID


def test_admin_tenant_header_ignored_single_org():
    store = StubStore({"k-admin": StubUser("admin-1", role="admin")})
    p = resolve_authenticated_principal(
        "k-admin", "admin", "impersonate-tenant", store
    )
    assert p.is_admin
    assert p.tenant_id == ORG_ID
