"""Tests for memory -> KB promotion pipeline."""
import asyncio

import pytest

from tars.memory.kb_promotion import (
    MIN_CHARS_FOR_AUTO_PROMOTE,
    MIN_ITEMS_FOR_AUTO_PROMOTE,
    default_promotion_group_id,
    group_ready,
    synthesize_note_markdown,
)


class TestGroupReady:
    def test_ready_by_count(self):
        assert group_ready({"count": MIN_ITEMS_FOR_AUTO_PROMOTE, "total_chars": 10})

    def test_ready_by_chars(self):
        assert group_ready({"count": 1, "total_chars": MIN_CHARS_FOR_AUTO_PROMOTE})

    def test_not_ready(self):
        assert not group_ready({"count": 1, "total_chars": 100})


class TestSynthesizeNote:
    def test_fallback_markdown(self):
        md = synthesize_note_markdown(
            [
                {"content": "SHOW TABLES 不能追加 LIMIT", "category": "domain_knowledge"},
                {"content": "仅 SELECT 自动 LIMIT", "category": "fact"},
            ],
            user_context="SQL 报错",
            provider=None,
        )
        assert "SHOW TABLES" in md
        assert "SELECT" in md
        assert md.startswith("#")


@pytest.mark.asyncio
async def test_save_does_not_publish_by_default(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tars.api.memory import init_memory_api, router
    from tars.database import Database
    from tars.memory.manager import MemoryManager

    db = Database(db_path=str(tmp_path / "promo.db"))
    manager = MemoryManager(db=db, provider=None, tenant_id="default")
    app = FastAPI()
    app.include_router(router)
    init_memory_api(db, manager)
    client = TestClient(app)

    resp = client.post(
        "/api/memory/save-from-turn",
        json={
            "items": [{"content": "测试要点 A：根因是 LIMIT 误加", "category": "domain_knowledge"}],
            "user_context": "show tables 报错",
            "publish_to_knowledge": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["saved"]) == 1
    assert body["knowledge_doc_ids"] == []
    assert body["promotion_trigger"] == "pending"
    assert body["promotion_group_id"]

    mem_id = body["saved"][0]["id"]
    mem = db.get_memory(mem_id)
    assert mem.kb_promotion_status == "pending"
    assert mem.promotion_group_id == body["promotion_group_id"]
