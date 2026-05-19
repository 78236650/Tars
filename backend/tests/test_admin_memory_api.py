import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client_and_db(tmp_path):
    from tars.api.admin import init_admin_api, router as admin_router
    from tars.api.memory import init_memory_api, router as memory_router
    from tars.database import Database
    from tars.memory.manager import MemoryManager

    db = Database(db_path=str(tmp_path / "admin-memory.db"))
    manager = MemoryManager(db, provider=None)
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(memory_router)
    init_admin_api(db)
    init_memory_api(db, manager)

    db.add_memory(content="用户 A 记忆", category="fact", tenant_id="user-a")
    db.add_memory(content="用户 B 记忆", category="fact", tenant_id="user-b")

    with TestClient(app) as client:
        yield client, db


def test_admin_users_response_shape(client_and_db):
    client, _db = client_and_db
    resp = client.get("/api/admin/memory/users", headers={"X-User-Role": "admin"})
    assert resp.status_code == 200
    payload = resp.json()
    assert "users" in payload
    tenant_ids = {item["tenant_id"] for item in payload["users"]}
    assert "user-a" in tenant_ids
    assert "user-b" in tenant_ids


def test_admin_user_memories_response_shape(client_and_db):
    client, _db = client_and_db
    resp = client.get("/api/admin/memory/users/user-a", headers={"X-User-Role": "admin"})
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload
    assert payload["total"] >= 1
    assert payload["tenant_id"] == "user-a"
    assert payload["items"][0]["summary"]
    assert payload["items"][0]["memory_type"] is not None


def test_admin_endpoints_require_admin_role(client_and_db):
    client, _db = client_and_db
    resp = client.get("/api/admin/memory/users", headers={"X-User-Role": "user"})
    assert resp.status_code == 403
