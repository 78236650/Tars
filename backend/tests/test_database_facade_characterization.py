"""Task 4: Database 表征测试 —— 拆分重构前的安全网。

拆分 base.py 后这些测试必须全部仍通过，证明对外签名零变更。
"""

import tempfile
import os
import pytest
from tars.database.base import Database


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    d = Database(db_path=path)
    yield d
    d.close()
    os.unlink(path)


def test_session_message_roundtrip(db):
    """会话与消息的创建/读取往返。"""
    s = db.create_session(user_id="u", tenant_id="t", title="hi")
    db.add_message(s.id, "user", "hello")
    msgs = db.get_messages(s.id)
    assert [m.content for m in msgs] == ["hello"]
    assert db.get_session(s.id, tenant_id="t").title == "hi"


def test_memory_crud_and_search(db):
    """记忆增删查。"""
    m = db.add_memory(content="user likes Go", category="user_preference", tenant_id="t")
    assert db.get_memory(m.id, tenant_id="t").content == "user likes Go"
    hits = db.search_memories("Go", limit=5, tenant_id="t")
    assert any("Go" in h.content for h in hits)


def test_cronjob_lifecycle(db):
    """定时任务生命周期。"""
    c = db.create_cronjob(
        user_id="u", name="job",
        cron_expression="* * * * *",
        task_type="prompt", task_config="x",
    )
    assert db.get_cronjob(c.id) is not None
    db.delete_cronjob(c.id)
    assert db.get_cronjob(c.id) is None


def test_working_context_upsert(db):
    """工作上下文写入与读取。"""
    db.upsert_working_context("sess1", tenant_id="t", current_intent="shipping")
    assert db.get_working_context("sess1", tenant_id="t").get("current_intent") == "shipping"
