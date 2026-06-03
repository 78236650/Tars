import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

import pytest

from tars.org import ORG_ID
from tars.memory.entity_id import compute_entity_id
from tars.memory.tree_builder import (
    EntityTreeBuilder,
    classify_bucket,
    normalize_entity_ref,
    primary_entity_id,
)


class StubLLMProvider:
    async def chat(self, messages, **kwargs):
        return {"content": "ok"}


def _seed_memory(
    db,
    *,
    content: str,
    category: str = "fact",
    importance: float = 0.5,
    memory_type: str = "episodic",
    pinned: int = 0,
    entity_refs=None,
    compressed_from=None,
):
    memory = db.add_memory(
        content=content,
        category=category,
        importance=importance,
        tenant_id=ORG_ID,
        user_id="tree-user",
    )
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE memories
        SET pinned = ?, memory_type = ?, entity_refs = ?, compressed_from = ?
        WHERE id = ?
        """,
        (
            pinned,
            memory_type,
            json.dumps(entity_refs, ensure_ascii=False) if entity_refs is not None else None,
            json.dumps(compressed_from, ensure_ascii=False) if compressed_from else None,
            memory.id,
        ),
    )
    conn.commit()
    return memory


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tars.api.memory import init_memory_api, router
    from tars.api._auth import Principal, require_authenticated_user
    from tars.config.memory import config as memory_config
    from tars.database import Database
    from tars.memory.manager import MemoryManager

    monkeypatch.setattr(memory_config, "tree_builder_enabled", True)
    db = Database(db_path=str(tmp_path / "tree.db"))
    manager = MemoryManager(db, provider=StubLLMProvider())
    app = FastAPI()

    from tars.context import set_request_context

    async def _fake_auth():
        set_request_context("tree-user", ORG_ID)
        return Principal(
            user_id="tree-user",
            role="admin",
            role_template_id="admin",
            tenant_id=ORG_ID,
            is_admin=True,
            api_key="test-key",
        )
    app.dependency_overrides[require_authenticated_user] = _fake_auth

    app.include_router(router)
    init_memory_api(db, manager)
    return TestClient(app), db


class TestNormalizeEntityRef:
    def test_string_id(self):
        eid, etype, _ = normalize_entity_ref("person:a1b2c3d4")
        assert eid == "person:a1b2c3d4"
        assert etype == "person"

    def test_dict_name_type(self):
        eid, etype, hint = normalize_entity_ref({"name": "Alice", "type": "person"})
        assert etype == "person"
        assert hint == "Alice"
        assert eid == compute_entity_id("person", "Alice")


class TestEntityTreeBuilder:
    def test_empty_tenant_has_core_only(self, client_and_db):
        _client, db = client_and_db
        builder = EntityTreeBuilder(db, tenant_id=ORG_ID)
        result = builder.build(include_orphan=False)
        assert result["stats"]["memory_count"] == 0
        assert any(n["id"] == "__core__" for n in result["nodes"])

    def test_groups_by_primary_entity(self, client_and_db):
        _client, db = client_and_db
        alice_id = compute_entity_id("person", "Alice")
        tars_id = compute_entity_id("project", "TARS")
        _seed_memory(
            db,
            content="Alice 偏好 TS",
            importance=0.8,
            memory_type="longterm",
            entity_refs=[alice_id, tars_id],
        )
        _seed_memory(
            db,
            content="TARS 使用 FastAPI",
            importance=0.7,
            memory_type="longterm",
            entity_refs=[tars_id],
        )
        result = EntityTreeBuilder(db, tenant_id=ORG_ID).build()
        assert result["stats"]["entity_count"] == 2
        person_group = next(n for n in result["nodes"] if n["id"] == "__type:person")
        alice = next(c for c in person_group["children"] if c["id"] == alice_id)
        longterm = next(c for c in alice["children"] if c["meta"]["bucket"] == "longterm")
        leaf = longterm["children"][0]
        assert leaf["kind"] == "memory"
        assert tars_id in leaf["meta"]["co_entities"]

    def test_orphan_bucket(self, client_and_db):
        _client, db = client_and_db
        _seed_memory(db, content="无实体记忆", entity_refs=[])
        result = EntityTreeBuilder(db, tenant_id=ORG_ID).build()
        assert result["stats"]["orphan_count"] == 1
        assert any(n["id"] == "__orphan__" for n in result["nodes"])

    def test_bucket_truncation(self, client_and_db):
        _client, db = client_and_db
        eid = compute_entity_id("person", "Bob")
        for i in range(35):
            _seed_memory(
                db,
                content=f"记忆 {i}",
                importance=0.8,
                memory_type="longterm",
                entity_refs=[eid],
            )
        result = EntityTreeBuilder(db, tenant_id=ORG_ID, max_per_bucket=30).build()
        person_group = next(n for n in result["nodes"] if n["id"] == "__type:person")
        bob = person_group["children"][0]
        longterm = next(c for c in bob["children"] if c["meta"]["bucket"] == "longterm")
        assert longterm["meta"]["truncated"] is True
        assert any(c["kind"] == "more" for c in longterm["children"])


class TestMemoryTreeAPI:
    def test_get_tree(self, client_and_db):
        client, db = client_and_db
        eid = compute_entity_id("project", "Demo")
        _seed_memory(db, content="demo", memory_type="longterm", importance=0.7, entity_refs=[eid])
        resp = client.get("/api/memory/tree")
        assert resp.status_code == 200
        body = resp.json()
        assert body["view"] == "entity"
        assert body["stats"]["memory_count"] >= 1

    def test_tree_admin_user_id_forbidden_for_non_admin(self, client_and_db):
        """Non-admin principal cannot use user_id to view another tenant."""
        from fastapi import HTTPException as _HTTPException
        from tars.api._auth import Principal
        from tars.api.memory import _resolve_tree_tenant

        from tars.org import ORG_ID

        non_admin = Principal(
            user_id="alice",
            role="user",
            role_template_id="standard",
            tenant_id=ORG_ID,
            is_admin=False,
            api_key="k",
        )
        with pytest.raises(_HTTPException) as exc:
            _resolve_tree_tenant(non_admin, "other")
        assert exc.value.status_code == 403

    def test_provenance_view(self, client_and_db):
        client, db = client_and_db
        eid = compute_entity_id("person", "Prov")
        src1 = _seed_memory(
            db,
            content="源记忆一",
            memory_type="longterm",
            importance=0.7,
            entity_refs=[eid],
        )
        src2 = _seed_memory(
            db,
            content="源记忆二",
            memory_type="longterm",
            importance=0.7,
            entity_refs=[eid],
        )
        compressed = _seed_memory(
            db,
            content="合并后的压缩摘要",
            memory_type="compressed",
            importance=0.8,
            entity_refs=[eid],
            compressed_from=[src1.id, src2.id, "deleted-id-000"],
        )
        resp = client.get("/api/memory/tree", params={"view": "provenance"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["view"] == "provenance"
        assert body["stats"]["compressed_count"] == 1
        assert body["stats"]["archived_count"] == 1
        root = body["nodes"][0]
        comp_node = next(c for c in root["children"] if c["id"] == compressed.id)
        assert len(comp_node["children"]) == 3
        assert any(c["kind"] == "archived" for c in comp_node["children"])

    def test_tree_search(self, client_and_db):
        client, db = client_and_db
        eid = compute_entity_id("project", "SearchDemo")
        _seed_memory(
            db,
            content="唯一搜索关键词 xyzzy",
            memory_type="longterm",
            importance=0.7,
            entity_refs=[eid],
        )
        resp = client.get("/api/memory/tree/search", params={"q": "xyzzy"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert any("xyzzy" in (it.get("label") or "").lower() for it in items)

    def test_tree_graph(self, client_and_db):
        from tars.org import ORG_ID

        client, db = client_and_db
        from_a = compute_entity_id("person", "GraphA")
        to_b = compute_entity_id("project", "GraphB")
        _seed_memory(
            db,
            content="A works on B",
            memory_type="longterm",
            importance=0.7,
            entity_refs=[from_a, to_b],
        )
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO relations(tenant_id, from_entity, to_entity, predicate, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ORG_ID, from_a, to_b, "works_on", 0.85, "2026-05-19T00:00:00+08:00"),
        )
        conn.commit()
        resp = client.get("/api/memory/tree/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stats"]["node_count"] >= 2
        assert body["stats"]["edge_count"] >= 1
        ids = {n["id"] for n in body["nodes"]}
        assert from_a in ids and to_b in ids

    def test_tree_relations(self, client_and_db):
        from tars.org import ORG_ID

        client, db = client_and_db
        from_a = compute_entity_id("person", "A")
        to_b = compute_entity_id("project", "B")
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO relations(tenant_id, from_entity, to_entity, predicate, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ORG_ID, from_a, to_b, "works_on", 0.9, "2026-05-19T00:00:00+08:00"),
        )
        conn.commit()
        resp = client.get("/api/memory/tree/relations", params={"entity_id": from_a})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["outgoing"]) == 1
        assert data["outgoing"][0]["predicate"] == "works_on"
