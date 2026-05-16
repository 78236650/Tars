import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

import pytest


class StubLLMProvider:
    async def chat(self, messages, **kwargs):
        return {"content": "压缩后的摘要：保留关键事实与偏好。"}


def _seed_memory(
    db,
    *,
    content: str,
    category: str = "fact",
    importance: float = 0.5,
    memory_type: str = "episodic",
    pinned: int = 0,
    entity_refs=None,
):
    memory = db.add_memory(content=content, category=category, importance=importance)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE memories
        SET pinned = ?, memory_type = ?, entity_refs = ?
        WHERE id = ?
        """,
        (
            pinned,
            memory_type,
            json.dumps(entity_refs, ensure_ascii=False) if entity_refs is not None else None,
            memory.id,
        ),
    )
    conn.commit()
    return memory


class TestMemoryManagementSchema:
    def test_memories_has_management_columns(self, tmp_path):
        from tars.database import Database

        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(memories)")
        cols = {row[1] for row in cursor.fetchall()}

        assert "pinned" in cols
        assert "compressed_from" in cols
        assert "memory_type" in cols
        assert "event_time" in cols
        assert "entity_refs" in cols


class TestMemoryManagementAPI:
    @pytest.fixture
    def client_and_db(self, tmp_path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from tars.api.memory import init_memory_api, router
        from tars.database import Database
        from tars.memory.manager import MemoryManager

        db = Database(db_path=str(tmp_path / "memory.db"))
        manager = MemoryManager(db, provider=StubLLMProvider())

        app = FastAPI()
        app.include_router(router)
        init_memory_api(db, manager)
        return TestClient(app), db, manager

    def test_core_memory_roundtrip(self, client_and_db):
        client, _db, manager = client_and_db

        before = client.get("/api/memory/core")
        assert before.status_code == 200
        assert "persona" in before.json()["blocks"]

        resp = client.put("/api/memory/core/persona", json={"content": "新的 TARS 自我认知"})
        assert resp.status_code == 200
        assert resp.json()["block"] == "persona"
        assert manager.core.get("persona") == "新的 TARS 自我认知"

    def test_recent_endpoint_filters_by_days_and_category(self, client_and_db):
        client, db, _manager = client_and_db

        keep = _seed_memory(
            db,
            content="最近 7 天内的开发偏好",
            category="fact",
            memory_type="episodic",
        )
        _seed_memory(
            db,
            content="近期但不同分类",
            category="decision",
            memory_type="episodic",
        )
        stale = _seed_memory(
            db,
            content="8 天前的旧记忆",
            category="fact",
            memory_type="episodic",
        )

        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE memories
            SET created_at = datetime('now', '-8 day'),
                updated_at = datetime('now', '-8 day')
            WHERE id = ?
            """,
            (stale.id,),
        )
        conn.commit()

        resp = client.get("/api/memory/recent?page=1&cat=fact")
        assert resp.status_code == 200
        payload = resp.json()
        ids = [item["id"] for item in payload["items"]]

        assert keep.id in ids
        assert stale.id not in ids
        assert payload["page"] == 1

    def test_longterm_endpoint_groups_records(self, client_and_db):
        client, db, _manager = client_and_db

        _seed_memory(
            db,
            content="Alice 偏好命令行工作流",
            importance=0.8,
            memory_type="longterm",
            entity_refs=["person:alice"],
        )
        _seed_memory(
            db,
            content="一条被 pin 的通用长期记忆",
            importance=0.3,
            memory_type="episodic",
            pinned=1,
        )

        resp = client.get("/api/memory/longterm?page=1&group_by=entity")
        assert resp.status_code == 200
        groups = resp.json()["groups"]

        group_names = {group["group_name"] for group in groups}
        assert "person:alice" in group_names
        assert "通用" in group_names

    def test_all_endpoint_includes_old_low_importance_records(self, client_and_db):
        client, db, _manager = client_and_db

        old_memory = _seed_memory(
            db,
            content="这是一条旧的低重要度记忆，也应该能在全部记忆里看到",
            category="fact",
            importance=0.1,
            memory_type="episodic",
        )
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE memories
            SET created_at = datetime('now', '-20 day'),
                updated_at = datetime('now', '-20 day')
            WHERE id = ?
            """,
            (old_memory.id,),
        )
        conn.commit()

        resp = client.get("/api/memory/all?page=1")
        assert resp.status_code == 200
        payload = resp.json()
        ids = [item["id"] for item in payload["items"]]

        assert old_memory.id in ids
        assert payload["total"] >= 1

    def test_all_endpoint_supports_memory_type_filter(self, client_and_db):
        client, db, _manager = client_and_db

        episodic = _seed_memory(db, content="可见的 episodic 记忆", memory_type="episodic")
        longterm = _seed_memory(db, content="可见的 longterm 记忆", memory_type="longterm", importance=0.8)

        resp = client.get("/api/memory/all?page=1&memory_type=longterm")
        assert resp.status_code == 200
        payload = resp.json()
        ids = [item["id"] for item in payload["items"]]

        assert longterm.id in ids
        assert episodic.id not in ids

    def test_pin_promote_update_delete_flow(self, client_and_db):
        client, db, _manager = client_and_db
        memory = _seed_memory(db, content="待编辑记忆", importance=0.4)

        pin_resp = client.post(f"/api/memory/{memory.id}/pin", json={"pinned": True})
        assert pin_resp.status_code == 200
        assert pin_resp.json()["pinned"] is True

        promote_resp = client.post(f"/api/memory/{memory.id}/promote")
        assert promote_resp.status_code == 200
        assert promote_resp.json()["memory_type"] == "longterm"

        update_resp = client.put(f"/api/memory/{memory.id}", json={"content": "编辑后的记忆内容"})
        assert update_resp.status_code == 200

        detail = client.get(f"/api/memory/{memory.id}")
        assert detail.status_code == 200
        assert detail.json()["content"] == "编辑后的记忆内容"

        delete_resp = client.delete(f"/api/memory/{memory.id}")
        assert delete_resp.status_code == 200

        missing = client.get(f"/api/memory/{memory.id}")
        assert missing.status_code == 404

    def test_merge_preview_and_confirm_replace_originals(self, client_and_db):
        client, db, _manager = client_and_db
        first = _seed_memory(
            db,
            content="用户偏好使用 Python 处理自动化脚本",
            importance=0.55,
            memory_type="longterm",
            entity_refs=["person:user"],
        )
        second = _seed_memory(
            db,
            content="用户在新项目中也优先选择 Python 技术栈",
            importance=0.65,
            memory_type="longterm",
            entity_refs=["person:user"],
        )

        preview_resp = client.post(
            "/api/memory/merge",
            json={"memory_ids": [first.id, second.id], "preview_only": True},
        )
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["preview_only"] is True
        assert "压缩后的摘要" in preview["merged_content"]

        confirm_resp = client.post(
            "/api/memory/merge",
            json={"memory_ids": [first.id, second.id], "preview_only": False},
        )
        assert confirm_resp.status_code == 200
        result = confirm_resp.json()
        assert result["preview_only"] is False
        assert result["memory"]["memory_type"] == "longterm"
        assert sorted(result["memory"]["compressed_from"]) == sorted([first.id, second.id])

        assert client.get(f"/api/memory/{first.id}").status_code == 404
        assert client.get(f"/api/memory/{second.id}").status_code == 404

    def test_manual_compress_updates_status(self, client_and_db):
        client, db, _manager = client_and_db

        for i in range(11):
            _seed_memory(
                db,
                content=f"Alice 第 {i} 条近期记忆",
                importance=0.45,
                memory_type="episodic",
                entity_refs=["person:alice"],
            )

        compress_resp = client.post("/api/memory/compress")
        assert compress_resp.status_code == 200
        report = compress_resp.json()
        assert report["status"] == "completed"
        assert report["compressed_count"] >= 1

        status_resp = client.get("/api/memory/compress/status")
        assert status_resp.status_code == 200
        status = status_resp.json()
        assert status["status"] == "completed"
        assert status["last_report"]["compressed_count"] >= 1
