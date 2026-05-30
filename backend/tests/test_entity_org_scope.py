"""TARS v5.0 Phase 2 Task T2.3 — entity graph is org-global (no tenant_id on entities)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime, timezone, timedelta

from tars.context import clear_request_context, set_request_context
from tars.database import Database
from tars.memory.entity_id import compute_entity_id
from tars.memory.tree_builder import EntityTreeBuilder, normalize_entity_ref
from tars.org import ORG_ID

_NOW = datetime.now(timezone(timedelta(hours=8))).isoformat()


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "entity_org_scope.db"))
    yield database
    database.close()
    clear_request_context()


def _insert_entity(database: Database, *, entity_id: str, name: str, etype: str = "terminal"):
    """Direct insert — entities table is global (no tenant_id)."""
    conn = database._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO entities(
            id, type, name, aliases, attributes, attributes_history,
            confidence, first_seen, last_seen, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            etype,
            name,
            json.dumps([name], ensure_ascii=False),
            "{}",
            "[]",
            0.9,
            _NOW,
            _NOW,
            _NOW,
            _NOW,
        ),
    )
    conn.commit()


def _fetch_entity(database: Database, entity_id: str):
    cur = database._get_conn().cursor()
    cur.execute("SELECT id, type, name FROM entities WHERE id = ?", (entity_id,))
    return cur.fetchone()


def test_entities_table_has_no_per_user_tenant_columns(db):
    cur = db._get_conn().cursor()
    cur.execute("PRAGMA table_info(entities)")
    columns = {row[1] for row in cur.fetchall()}
    assert "tenant_id" not in columns
    assert "user_id" not in columns


def test_user_b_reads_entity_created_by_user_a(db):
    qc7_id = compute_entity_id("terminal", "QC-7")

    set_request_context("user-a", ORG_ID)
    _insert_entity(db, entity_id=qc7_id, name="QC-7", etype="terminal")
    clear_request_context()

    set_request_context("user-b", ORG_ID)
    row = _fetch_entity(db, qc7_id)
    assert row is not None
    assert row[0] == qc7_id
    assert row[1] == "terminal"
    assert row[2] == "QC-7"
    clear_request_context()


def test_user_b_tree_builder_resolves_entity_label(db):
    qc7_ref = {"name": "QC-7", "type": "terminal"}
    qc7_id, _, _ = normalize_entity_ref(qc7_ref)

    set_request_context("user-a", ORG_ID)
    _insert_entity(db, entity_id=qc7_id, name="QC-7", etype="terminal")
    db.add_memory(
        content="QC-7 berth assignment at B12",
        category="fact",
        scope="shared",
        tenant_id=ORG_ID,
        user_id=None,
        entity_refs=[qc7_ref],
    )
    clear_request_context()

    set_request_context("user-b", ORG_ID)
    memories = db.list_memories_for_tree(tenant_id=ORG_ID, limit=100)
    labels = EntityTreeBuilder(db, tenant_id=ORG_ID)._load_entity_labels(memories)
    assert labels.get(qc7_id) == "QC-7"
    clear_request_context()


def test_user_b_searches_shared_memory_linked_to_entity(db):
    qc7_ref = {"name": "QC-7", "type": "terminal"}

    set_request_context("user-a", ORG_ID)
    db.add_memory(
        content="QC-7 completed crane maintenance check",
        category="fact",
        scope="shared",
        tenant_id=ORG_ID,
        user_id=None,
        entity_refs=[qc7_ref],
    )
    clear_request_context()

    set_request_context("user-b", ORG_ID)
    hits = db.search_memories("crane maintenance", tenant_id=ORG_ID, user_id="user-b")
    assert any("QC-7 completed crane maintenance" in m.content for m in hits)
    clear_request_context()


def test_user_b_cannot_search_private_memory_linked_to_entity(db):
    qc7_ref = {"name": "QC-7", "type": "terminal"}

    set_request_context("user-a", ORG_ID)
    db.add_memory(
        content="QC-7 private operator note",
        category="fact",
        scope="private",
        tenant_id=ORG_ID,
        user_id="user-a",
        entity_refs=[qc7_ref],
    )
    clear_request_context()

    set_request_context("user-b", ORG_ID)
    hits = db.search_memories("private operator", tenant_id=ORG_ID, user_id="user-b")
    assert not any("QC-7 private operator note" in m.content for m in hits)
    clear_request_context()
