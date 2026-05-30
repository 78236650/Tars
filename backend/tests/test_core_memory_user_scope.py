"""TARS v5.0 Phase 2 Task T2.4 — core_memory_blocks per-user isolation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.context import clear_request_context, set_request_context
from tars.database.base import Database
from tars.memory.core_memory import CoreMemoryManager
from tars.org import ORG_ID


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "core_memory_user_scope.db"))
    yield database
    database.close()
    clear_request_context()


def test_persona_isolated_between_users(db):
    cm_a = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-a")
    cm_a.set("persona", "Persona for user A")

    cm_b = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-b")
    assert cm_b.get("persona") == ""
    assert "Persona for user A" not in cm_b.get("persona")

    cm_a_again = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-a")
    assert cm_a_again.get("persona") == "Persona for user A"


def test_user_b_does_not_inherit_default_seed(db):
    cm_default = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="default")
    assert "TARS" in cm_default.get("persona")

    cm_b = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-b")
    assert cm_b.get("persona") == ""


def test_set_via_request_context(db):
    set_request_context("user-a")
    cm = CoreMemoryManager(db, tenant_id=ORG_ID)
    cm.set("user_profile", "Alice likes Go")
    clear_request_context()

    set_request_context("user-b")
    other = CoreMemoryManager(db, tenant_id=ORG_ID)
    assert other.get("user_profile") == ""
    clear_request_context()

    reader = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-a")
    assert "Alice likes Go" in reader.get("user_profile")


def test_forget_core_line_scoped_to_user(db):
    cm_a = CoreMemoryManager(db, tenant_id=ORG_ID, user_id="user-a")
    cm_a.set("working_principles", "line one\nsecret line\nline three")

    assert db.forget_core_line(
        "working_principles",
        "secret line",
        tenant_id=ORG_ID,
        user_id="user-b",
    ) is False

    assert db.forget_core_line(
        "working_principles",
        "secret line",
        tenant_id=ORG_ID,
        user_id="user-a",
    ) is True
    assert "secret line" not in cm_a.get("working_principles")
