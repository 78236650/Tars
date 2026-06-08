"""记忆系统升级：双向链接 + 分层检索 验证。"""
import pytest

from tars.org import ORG_ID


def test_wiki_pages_upsert_and_reverse_lookup(test_db):
    """wiki_pages 写入后，能按 memory_id 反查到 wiki 页。"""
    db = test_db
    db.upsert_wiki_page(
        "memory-abc12345",
        title="PostgreSQL 连接池笔记",
        summary="连接池耗尽排查",
        source_memory_ids=["mem-1", "mem-2", "mem-3"],
        source_type="chat_remember",
    )

    meta = db.get_wiki_page_meta("memory-abc12345")
    assert meta is not None
    assert meta["title"] == "PostgreSQL 连接池笔记"
    assert meta["source_memory_ids"] == ["mem-1", "mem-2", "mem-3"]
    assert meta["source_type"] == "chat_remember"

    # 反查：每个源记忆都能找到这页
    for mid in ["mem-1", "mem-2", "mem-3"]:
        pages = db.find_pages_by_memory_id(mid)
        assert any(p["page_name"] == "memory-abc12345" for p in pages)

    # 不相关的 id 查不到
    assert db.find_pages_by_memory_id("mem-999") == []


def test_reverse_lookup_no_substring_false_positive(test_db):
    """LIKE 包含匹配后须二次校验，避免子串误命中（mem-1 不应命中 mem-12）。"""
    db = test_db
    db.upsert_wiki_page(
        "memory-page-x",
        title="t",
        summary="s",
        source_memory_ids=["mem-12"],
        source_type="chat_remember",
    )
    # mem-1 是 mem-12 的子串，但不应反查命中
    assert db.find_pages_by_memory_id("mem-1") == []
    assert any(p["page_name"] == "memory-page-x" for p in db.find_pages_by_memory_id("mem-12"))


def test_upsert_is_idempotent_update(test_db):
    """同 page_name 再次 upsert 走更新而非重复插入。"""
    db = test_db
    db.upsert_wiki_page("memory-dup", title="v1", summary="s", source_memory_ids=["a"])
    db.upsert_wiki_page("memory-dup", title="v2", summary="s2", source_memory_ids=["a", "b"])
    meta = db.get_wiki_page_meta("memory-dup")
    assert meta["title"] == "v2"
    assert meta["source_memory_ids"] == ["a", "b"]
