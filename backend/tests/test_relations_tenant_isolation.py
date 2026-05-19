"""Verify that all relation reads in EntityTreeBuilder are tenant-scoped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.database import Database
from tars.memory.entity_id import compute_entity_id
from tars.memory.tree_builder import EntityTreeBuilder


def _insert_relation(db, *, tenant_id, from_id, to_id, predicate, confidence=0.7):
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO relations(tenant_id, from_entity, to_entity, predicate, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tenant_id, from_id, to_id, predicate, confidence, "2026-05-19T00:00:00+08:00"),
    )
    conn.commit()


@pytest.fixture
def db(tmp_path):
    return Database(db_path=str(tmp_path / "rel.db"))


def test_same_relation_in_two_tenants_does_not_conflict(db):
    a = compute_entity_id("person", "A")
    b = compute_entity_id("project", "B")
    _insert_relation(db, tenant_id="t1", from_id=a, to_id=b, predicate="works_on")
    _insert_relation(db, tenant_id="t2", from_id=a, to_id=b, predicate="works_on")

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM relations")
    assert cur.fetchone()[0] == 2


def test_get_relations_only_returns_own_tenant(db):
    a = compute_entity_id("person", "A")
    b = compute_entity_id("project", "B")
    _insert_relation(db, tenant_id="t1", from_id=a, to_id=b, predicate="works_on")
    _insert_relation(db, tenant_id="t2", from_id=a, to_id=b, predicate="uses")

    t1 = EntityTreeBuilder(db, tenant_id="t1")
    relations = t1.get_relations(a)
    assert len(relations["outgoing"]) == 1
    assert relations["outgoing"][0]["predicate"] == "works_on"

    t2 = EntityTreeBuilder(db, tenant_id="t2")
    relations2 = t2.get_relations(a)
    assert len(relations2["outgoing"]) == 1
    assert relations2["outgoing"][0]["predicate"] == "uses"


def test_count_relations_is_tenant_scoped(db):
    a = compute_entity_id("person", "A")
    b = compute_entity_id("project", "B")
    _insert_relation(db, tenant_id="t1", from_id=a, to_id=b, predicate="p1")
    _insert_relation(db, tenant_id="t1", from_id=a, to_id=b, predicate="p2")
    _insert_relation(db, tenant_id="t2", from_id=a, to_id=b, predicate="p3")

    assert EntityTreeBuilder(db, tenant_id="t1")._count_relations() == 2
    assert EntityTreeBuilder(db, tenant_id="t2")._count_relations() == 1
    assert EntityTreeBuilder(db, tenant_id="t3")._count_relations() == 0


def test_build_graph_filters_relations_by_tenant(db):
    a = compute_entity_id("person", "A")
    b = compute_entity_id("project", "B")
    # Insert entities so build_graph picks them up via memories
    import json
    import datetime
    conn = db._get_conn()
    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for tenant_id in ("t1", "t2"):
        cur.execute(
            """
            INSERT INTO memories(id, tenant_id, content, category, importance, created_at, updated_at, memory_type, entity_refs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"m-{tenant_id}",
                tenant_id,
                f"memory for {tenant_id}",
                "fact",
                0.7,
                now,
                now,
                "longterm",
                json.dumps([a, b]),
            ),
        )
    conn.commit()

    _insert_relation(db, tenant_id="t1", from_id=a, to_id=b, predicate="t1_edge")
    _insert_relation(db, tenant_id="t2", from_id=a, to_id=b, predicate="t2_edge")

    g1 = EntityTreeBuilder(db, tenant_id="t1").build_graph()
    preds1 = [e["predicate"] for e in g1["edges"]]
    assert preds1 == ["t1_edge"]

    g2 = EntityTreeBuilder(db, tenant_id="t2").build_graph()
    preds2 = [e["predicate"] for e in g2["edges"]]
    assert preds2 == ["t2_edge"]
