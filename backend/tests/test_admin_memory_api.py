import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.org import ORG_ID


@pytest.fixture
def client_and_db(tmp_path):
    from tars.api._auth import get_user_store
    from tars.api.admin import init_admin_api, router as admin_router
    from tars.api.memory import init_memory_api, router as memory_router
    from tars.database import Database
    from tars.database.auth_token_store import AuthTokenStore
    from tars.memory.manager import MemoryManager
    from tars.middleware.user_context import UserContextMiddleware

    from tests.conftest import setup_admin_auth, setup_main_api_auth

    db = Database(db_path=str(tmp_path / "admin-memory.db"))
    admin_headers, _admin = setup_admin_auth(db)
    user_headers, _user = setup_main_api_auth(db)
    manager = MemoryManager(db, provider=None)
    app = FastAPI()
    store = get_user_store()
    app.state.user_store = store
    app.state.auth_token_store = AuthTokenStore(db)
    app.add_middleware(UserContextMiddleware)
    app.include_router(admin_router)
    app.include_router(memory_router)
    init_admin_api(db)
    init_memory_api(db, manager)

    db.add_memory(content="用户 A 记忆", category="fact", tenant_id=ORG_ID, user_id="user-a")
    db.add_memory(content="用户 B 记忆", category="fact", tenant_id=ORG_ID, user_id="user-b")

    with TestClient(app) as client:
        yield client, db, admin_headers, user_headers


def test_admin_users_response_shape(client_and_db):
    client, _db, admin_headers, _user_headers = client_and_db
    resp = client.get("/api/admin/memory/users", headers=admin_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert "users" in payload
    tenant_ids = {item["tenant_id"] for item in payload["users"]}
    assert "user-a" in tenant_ids
    assert "user-b" in tenant_ids


def test_admin_user_memories_response_shape(client_and_db):
    client, _db, admin_headers, _user_headers = client_and_db
    resp = client.get("/api/admin/memory/users/user-a", headers=admin_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload
    assert payload["total"] >= 1
    assert payload["tenant_id"] == ORG_ID
    assert payload["user_id"] == "user-a"
    assert payload["items"][0]["summary"]
    assert payload["items"][0]["memory_type"] is not None


def test_admin_endpoints_require_admin_role(client_and_db):
    client, _db, _admin_headers, user_headers = client_and_db
    resp = client.get("/api/admin/memory/users", headers=user_headers)
    assert resp.status_code == 403
