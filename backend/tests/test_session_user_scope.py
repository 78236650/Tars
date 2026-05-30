"""TARS v5.0 Phase 2 Task T2.4 — session user isolation."""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.api._auth import Principal, require_authenticated_user
from tars.api.sessions import init_sessions_api, router
from tars.context import clear_request_context, set_request_context
from tars.database.base import Database
from tars.org import ORG_ID


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "session_user_scope.db"))
    yield database
    database.close()
    clear_request_context()


def test_list_sessions_scoped_to_user(db):
    db.create_session(user_id="user-a", tenant_id=ORG_ID, title="A1")
    db.create_session(user_id="user-a", tenant_id=ORG_ID, title="A2")
    db.create_session(user_id="user-b", tenant_id=ORG_ID, title="B1")

    a_sessions = db.list_sessions(user_id="user-a", tenant_id=ORG_ID)
    b_sessions = db.list_sessions(user_id="user-b", tenant_id=ORG_ID)

    assert len(a_sessions) == 2
    assert len(b_sessions) == 1
    assert all(s.user_id == "user-a" for s in a_sessions)
    assert b_sessions[0].title == "B1"


def test_get_session_not_visible_to_other_user(db):
    session = db.create_session(user_id="user-a", tenant_id=ORG_ID, title="Private")

    assert db.get_session(session.id, tenant_id=ORG_ID, user_id="user-a") is not None
    assert db.get_session(session.id, tenant_id=ORG_ID, user_id="user-b") is None


def test_delete_session_requires_matching_user(db):
    session = db.create_session(user_id="user-a", tenant_id=ORG_ID, title="Mine")
    db.add_message(session.id, "user", "hello")

    assert db.delete_session(session.id, tenant_id=ORG_ID, user_id="user-b") is False
    assert db.get_session(session.id, tenant_id=ORG_ID, user_id="user-a") is not None

    assert db.delete_session(session.id, tenant_id=ORG_ID, user_id="user-a") is True
    assert db.get_session(session.id, tenant_id=ORG_ID, user_id="user-a") is None


def test_update_session_title_requires_matching_user(db):
    session = db.create_session(user_id="user-a", tenant_id=ORG_ID, title="Old")

    assert db.update_session_title(session.id, "New", tenant_id=ORG_ID, user_id="user-b") is False
    assert db.update_session_title(session.id, "New", tenant_id=ORG_ID, user_id="user-a") is True
    assert db.get_session(session.id, tenant_id=ORG_ID, user_id="user-a").title == "New"


def test_list_sessions_uses_request_context_when_user_id_omitted(db):
    set_request_context("user-a")
    s = db.create_session(user_id="user-a", tenant_id=ORG_ID, title="Ctx")
    db.create_session(user_id="user-b", tenant_id=ORG_ID, title="Other")

    sessions = db.list_sessions(tenant_id=ORG_ID)
    assert len(sessions) == 1
    assert sessions[0].id == s.id
    clear_request_context()


@pytest.fixture
def sessions_client(db):
    app = FastAPI()
    app.include_router(router)
    init_sessions_api(db)

    current_user = {"user_id": "default"}

    async def _dep():
        return Principal(
            user_id=current_user["user_id"],
            role="user",
            role_template_id="standard",
            tenant_id=ORG_ID,
            is_admin=False,
            api_key=f"key-{current_user['user_id']}",
        )

    app.dependency_overrides[require_authenticated_user] = _dep
    client = TestClient(app)

    def as_user(user_id: str) -> TestClient:
        current_user["user_id"] = user_id
        return client

    yield as_user
    app.dependency_overrides.clear()


def test_api_sessions_isolated_by_authenticated_user(sessions_client):
    client = sessions_client("user-a")

    created = client.post("/api/sessions/").json()
    client.post("/api/sessions/")

    list_a = sessions_client("user-a").get("/api/sessions/").json()
    list_b = sessions_client("user-b").get("/api/sessions/").json()

    assert len(list_a) == 2
    assert list_b == []
    assert sessions_client("user-b").get(f"/api/sessions/{created['id']}/messages").status_code == 404
