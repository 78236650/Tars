from fastapi import FastAPI
from fastapi.testclient import TestClient

from tars.api.invoke import router, init_invoke_api
from tars.database import Database, UserStore
from tars.gateway.permission import UserRole
from tars.tenant.context import TenantContextCache


class FakeMemoryManager:
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id

    def for_tenant(self, tenant_id: str):
        return FakeMemoryManager(tenant_id=tenant_id)


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def handle_message(
        self,
        session_id: str,
        user_content: str,
        channel,
        file_ids=None,
        tenant_context=None,
        request_context=None,
    ):
        self.calls.append(
            {
                "session_id": session_id,
                "user_content": user_content,
                "tenant_id": tenant_context.tenant_id if tenant_context else None,
            }
        )
        await channel.send(
            session_id,
            {
                "type": "text_chunk",
                "session_id": session_id,
                "content": "pong",
            },
        )
        await channel.send(
            session_id,
            {
                "type": "done",
                "session_id": session_id,
                "model": "fake-model",
            },
        )


def test_tenant_context_cache_reuses_context():
    memory_manager = FakeMemoryManager()
    cache = TenantContextCache(max_size=2)

    ctx1 = cache.get_or_create("tenant_a", lambda tenant_id: memory_manager.for_tenant(tenant_id))
    ctx2 = cache.get_or_create("tenant_a", lambda tenant_id: memory_manager.for_tenant(tenant_id))

    assert ctx1 is ctx2
    assert ctx1.tenant_id == "tenant_a"
    assert ctx1.memory_manager.tenant_id == "tenant_a"


def test_invoke_api_uses_org_scope_context():
    from tars.org import ORG_ID

    app = FastAPI()
    app.include_router(router)

    agent = FakeAgent()
    cache = TenantContextCache(max_size=4)
    init_invoke_api(agent=agent, tenant_cache=cache, memory_manager=FakeMemoryManager())

    client = TestClient(app)
    response = client.post(
        "/api/invoke",
        headers={"X-Tenant-Id": "tenant_a"},  # ignored under v5.0 single org
        json={"message": "ping", "session_id": "sess-1", "stream": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "pong"
    assert data["session_id"] == "sess-1"
    assert agent.calls[0]["tenant_id"] == ORG_ID


def test_invoke_api_streams_sse_events():
    app = FastAPI()
    app.include_router(router)

    agent = FakeAgent()
    cache = TenantContextCache(max_size=4)
    init_invoke_api(agent=agent, tenant_cache=cache, memory_manager=FakeMemoryManager())

    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/invoke",
        headers={"X-Tenant-Id": "tenant_stream"},
        json={"message": "ping", "session_id": "sess-stream", "stream": True},
    ) as response:
        body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert "event: text_chunk" in body
    assert '"content": "pong"' in body
    assert "event: done" in body


def test_invoke_api_rejects_missing_api_key(tmp_path):
    app = FastAPI()
    app.include_router(router)

    db = Database(db_path=str(tmp_path / "invoke-auth.db"))
    user_store = UserStore(db)
    init_invoke_api(
        agent=FakeAgent(),
        tenant_cache=TenantContextCache(max_size=4),
        memory_manager=FakeMemoryManager(),
        user_store=user_store,
    )

    client = TestClient(app)
    response = client.post(
        "/api/invoke",
        headers={"X-Tenant-Id": "tenant_auth"},
        json={"message": "ping", "session_id": "sess-auth", "stream": False},
    )

    assert response.status_code == 401


def test_invoke_api_accepts_valid_bearer_api_key(tmp_path):
    app = FastAPI()
    app.include_router(router)

    db = Database(db_path=str(tmp_path / "invoke-auth.db"))
    user_store = UserStore(db)
    user = user_store.create_user("alice", "alice@example.com", role=UserRole.USER)
    agent = FakeAgent()
    init_invoke_api(
        agent=agent,
        tenant_cache=TenantContextCache(max_size=4),
        memory_manager=FakeMemoryManager(),
        user_store=user_store,
    )

    client = TestClient(app)
    response = client.post(
        "/api/invoke",
        headers={
            "X-Tenant-Id": user.id,
            "Authorization": f"Bearer {user.api_key}",
        },
        json={"message": "ping", "session_id": "sess-auth", "stream": False},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "pong"
    from tars.org import ORG_ID

    assert agent.calls[0]["tenant_id"] == ORG_ID
