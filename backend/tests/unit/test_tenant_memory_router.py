from tars.database import Database
from tars.memory.manager import MemoryManager
from tars.memory.router import MemoryRouter
from tars.memory.working_context import WorkingContextManager


def test_working_context_is_isolated_by_tenant(tmp_path):
    db = Database(db_path=str(tmp_path / "tenant-memory.db"))
    wc_a = WorkingContextManager(db, tenant_id="tenant_a")
    wc_b = WorkingContextManager(db, tenant_id="tenant_b")

    wc_a.update("shared-session", current_intent="intent-a", focus_entities=["entity-a"])
    wc_b.update("shared-session", current_intent="intent-b", focus_entities=["entity-b"])

    assert wc_a.get("shared-session")["current_intent"] == "intent-a"
    assert wc_b.get("shared-session")["current_intent"] == "intent-b"
    assert wc_a.get("shared-session")["focus_entities"] == ["entity-a"]
    assert wc_b.get("shared-session")["focus_entities"] == ["entity-b"]


def test_memory_manager_for_tenant_keeps_core_memory_isolated(tmp_path):
    db = Database(db_path=str(tmp_path / "tenant-memory.db"))

    tenant_a = MemoryManager(db=db, provider=None).for_tenant("tenant_a")
    tenant_b = MemoryManager(db=db, provider=None).for_tenant("tenant_b")

    tenant_a.core.set("user_profile", "tenant-a-profile")
    tenant_b.core.set("user_profile", "tenant-b-profile")

    assert tenant_a.core.get("user_profile") == "tenant-a-profile"
    assert tenant_b.core.get("user_profile") == "tenant-b-profile"


def test_memory_router_keyword_route_respects_tenant(tmp_path):
    from tars.context import set_request_context
    from tars.org import ORG_ID

    db = Database(db_path=str(tmp_path / "tenant-memory.db"))
    set_request_context("user_a", ORG_ID)
    db.add_memory(content="tenant a docker", category="general", tenant_id=ORG_ID)
    set_request_context("user_b", ORG_ID)
    db.add_memory(content="tenant b docker", category="general", tenant_id=ORG_ID)

    set_request_context("user_a", ORG_ID)
    router_a = MemoryRouter(db, embedding_provider=None, tenant_id=ORG_ID)
    ctx_a = router_a.retrieve("docker", {}, limit=3)
    set_request_context("user_b", ORG_ID)
    router_b = MemoryRouter(db, embedding_provider=None, tenant_id=ORG_ID)
    ctx_b = router_b.retrieve("docker", {}, limit=3)

    assert "tenant a docker" in "\n".join(ctx_a["knowledge"])
    assert "tenant b docker" not in "\n".join(ctx_a["knowledge"])
    assert "tenant b docker" in "\n".join(ctx_b["knowledge"])
