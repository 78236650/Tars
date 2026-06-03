from tars.database import Database


def test_sessions_are_isolated_by_tenant(tmp_path):
    db = Database(db_path=str(tmp_path / "tenant.db"))

    session_a = db.create_session(user_id="u1", title="Tenant A", tenant_id="tenant_a")
    session_b = db.create_session(user_id="u1", title="Tenant B", tenant_id="tenant_b")

    assert db.get_session(session_a.id, tenant_id="tenant_a", user_id="u1") is not None
    assert db.get_session(session_a.id, tenant_id="tenant_b", user_id="u1") is None

    tenant_a_sessions = db.list_sessions(user_id="u1", tenant_id="tenant_a")
    tenant_b_sessions = db.list_sessions(user_id="u1", tenant_id="tenant_b")

    assert [item.id for item in tenant_a_sessions] == [session_a.id]
    assert [item.id for item in tenant_b_sessions] == [session_b.id]


def test_memories_are_isolated_by_tenant(tmp_path):
    from tars.context import set_request_context
    from tars.org import ORG_ID

    db = Database(db_path=str(tmp_path / "tenant.db"))

    set_request_context("user_a", ORG_ID)
    db.add_memory(content="tenant a memory", category="general", tenant_id=ORG_ID)
    set_request_context("user_b", ORG_ID)
    db.add_memory(content="tenant b memory", category="general", tenant_id=ORG_ID)

    set_request_context("user_a", ORG_ID)
    user_a_hits = db.search_memories("memory", tenant_id=ORG_ID)
    set_request_context("user_b", ORG_ID)
    user_b_hits = db.search_memories("memory", tenant_id=ORG_ID)

    assert [item.content for item in user_a_hits] == ["tenant a memory"]
    assert [item.content for item in user_b_hits] == ["tenant b memory"]
