"""TARS v5.0 Phase 2 Task T2.1 — org-scoped memory filtering."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.context import clear_request_context, set_request_context
from tars.database.base import Database
from tars.org import ORG_ID


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "memory_org_scope.db"))
    yield database
    database.close()
    clear_request_context()


def test_private_memory_not_visible_to_other_user(db):
    set_request_context("user-a")
    db.add_memory(
        content="User A private secret",
        category="fact",
        scope="private",
        tenant_id=ORG_ID,
        user_id="user-a",
    )
    clear_request_context()

    set_request_context("user-b")
    results = db.search_memories("secret", tenant_id=ORG_ID, user_id="user-b")
    assert not any("User A private secret" in m.content for m in results)
    clear_request_context()


def test_shared_memory_visible_to_other_user(db):
    set_request_context("user-a")
    db.add_memory(
        content="Org-wide shared fact",
        category="fact",
        scope="shared",
        tenant_id=ORG_ID,
        user_id=None,
    )
    clear_request_context()

    set_request_context("user-b")
    results = db.search_memories("Org-wide", tenant_id=ORG_ID, user_id="user-b")
    assert any("Org-wide shared fact" in m.content for m in results)
    clear_request_context()


def test_user_sees_own_private_and_shared(db):
    set_request_context("user-a")
    db.add_memory(
        content="User A private note",
        category="fact",
        scope="private",
        tenant_id=ORG_ID,
        user_id="user-a",
    )
    db.add_memory(
        content="User A shared note",
        category="fact",
        scope="shared",
        tenant_id=ORG_ID,
        user_id=None,
    )

    private_hits = db.search_memories("private note", tenant_id=ORG_ID, user_id="user-a")
    shared_hits = db.search_memories("shared note", tenant_id=ORG_ID, user_id="user-a")

    assert any("User A private note" in m.content for m in private_hits)
    assert any("User A shared note" in m.content for m in shared_hits)
    clear_request_context()
