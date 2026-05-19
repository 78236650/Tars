"""TARS Memory V3 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestSchemaMigration:
    def test_core_memory_blocks_table(self, tmp_path):
        from tars.database import Database
        db_path = str(tmp_path / "test.db")
        db = Database(db_path=db_path)
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM core_memory_blocks ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        assert names == ["persona", "project_context", "user_profile", "working_principles"]

        # 验证默认内容已被 INSERT OR IGNORE 写入（persona 块包含 TARS）
        cursor.execute("SELECT content FROM core_memory_blocks WHERE name = ?", ("persona",))
        persona_content = cursor.fetchone()[0]
        assert "TARS" in persona_content

    def test_memories_has_access_count_and_source(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(memories)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "access_count" in cols
        assert "source" in cols

    def test_reinit_idempotent(self, tmp_path):
        """重复初始化同一数据库不应报错，且 INSERT OR IGNORE / ALTER TABLE 都应幂等。"""
        from tars.database import Database
        db_path = str(tmp_path / "test.db")

        db1 = Database(db_path=db_path)
        db1.close()

        # 第二次初始化不应抛出错误（ALTER TABLE 重复添加列、INSERT OR IGNORE 重复插入都应被吸收）
        db2 = Database(db_path=db_path)
        conn = db2._get_conn()
        cursor = conn.cursor()

        # 仍然只有 4 行 core_memory_blocks
        cursor.execute("SELECT COUNT(*) FROM core_memory_blocks")
        assert cursor.fetchone()[0] == 4

        # access_count 和 source 列仍然存在（说明 ALTER TABLE 没有失败导致后续语句中断）
        cursor.execute("PRAGMA table_info(memories)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "access_count" in cols
        assert "source" in cols

        db2.close()


class TestCoreMemoryManager:
    def test_get_default(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        assert "TARS" in cm.get("persona")
        assert cm.get("nonexistent") == ""

    def test_replace(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        ok = cm.replace("user_profile", "old", "用户：张三")
        # 默认值不含 "old"，replace 行为应直接覆盖
        cm.set("user_profile", "用户喜欢 Python")
        ok = cm.replace("user_profile", "Python", "Go")
        assert ok is True
        assert "Go" in cm.get("user_profile")

    def test_append(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("working_principles", "")
        cm.append("working_principles", "不要主动改文档")
        cm.append("working_principles", "commit 前必须问")
        content = cm.get("working_principles")
        assert "不要主动改文档" in content
        assert "commit 前必须问" in content

    def test_trim_when_oversized(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db, max_size=100)
        cm.set("persona", "")
        for i in range(50):
            cm.append("persona", f"line {i} 占位文本占位文本")
        content = cm.get("persona")
        assert len(content.encode("utf-8")) <= 100
        # 应保留最新内容
        assert "line 49" in content

    def test_render_for_prompt(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("persona", "TARS")
        cm.set("user_profile", "用户 A")
        rendered = cm.render_for_prompt()
        assert "## 核心记忆" in rendered
        assert "### Persona" in rendered
        assert "TARS" in rendered
        assert "### User Profile" in rendered


class TestCoreMemoryTools:
    @pytest.mark.asyncio
    async def test_append_tool(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryAppendTool
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db, tenant_id="tenant-a")
        cm.set("user_profile", "")
        tool = CoreMemoryAppendTool(db)
        result = await tool.execute(
            block="user_profile",
            content="用户使用 Mac M1",
            tenant_id="tenant-a",
        )
        assert result.success is True
        assert "Mac M1" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_replace_tool(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryReplaceTool
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("user_profile", "用户使用 Python")
        tool = CoreMemoryReplaceTool(db)
        result = await tool.execute(
            block="user_profile",
            old="Python",
            new="Go",
            tenant_id="default",
        )
        assert result.success is True
        assert "Go" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_invalid_block_rejected(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryAppendTool
        db = Database(db_path=str(tmp_path / "t.db"))
        tool = CoreMemoryAppendTool(db)
        result = await tool.execute(block="invalid_block", content="x", tenant_id="default")
        assert result.success is False


class TestDecay:
    def test_recent_higher_than_old(self):
        from tars.memory.decay import decay_score
        recent_score = decay_score(similarity=0.7, importance=0.5, age_hours=1)
        old_score = decay_score(similarity=0.7, importance=0.5, age_hours=720)
        assert recent_score > old_score

    def test_high_importance_decays_slower(self):
        from tars.memory.decay import decay_score
        high = decay_score(similarity=0.7, importance=0.9, age_hours=720)
        low = decay_score(similarity=0.7, importance=0.2, age_hours=720)
        assert high > low

    def test_score_bounded(self):
        from tars.memory.decay import decay_score
        score = decay_score(similarity=1.0, importance=1.0, age_hours=0)
        assert 0 <= score <= 1.0001  # 允许浮点误差


class TestArchival:
    @pytest.mark.asyncio
    async def test_insert_with_source(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        mem = await am.insert(
            content="用户使用 Mac M1",
            category="fact",
            importance=0.7,
            source="conversation",
        )
        assert mem is not None
        assert mem.id

    @pytest.mark.asyncio
    async def test_reinforce(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        mem = await am.insert(content="测试事实数据", category="fact", importance=0.5, source="conversation")
        am.reinforce(mem.id)
        am.reinforce(mem.id)
        # 重新读取应看到 access_count >= 2 且 importance 微增
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT access_count, importance FROM memories WHERE id = ?", (mem.id,))
        row = cur.fetchone()
        assert row[0] >= 2
        assert row[1] > 0.5

    @pytest.mark.asyncio
    async def test_dedup_skips_duplicate(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        m1 = await am.insert(content="用户使用 Python", category="fact", importance=0.5, source="conversation")
        m2 = await am.insert(content="用户使用 Python", category="fact", importance=0.5, source="conversation")
        assert m1 is not None
        # 完全重复应返回 None
        assert m2 is None


class TestDecaySearch:
    @pytest.mark.asyncio
    async def test_search_reinforces_hits(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        from tars.memory.search import HybridSearch
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        m = await am.insert(content="用户使用 Mac M1 笔记本", category="fact", importance=0.5, source="conversation")
        search = HybridSearch(db, embedding_provider=None)
        results = search.search("Mac M1", limit=5)
        assert any(r.id == m.id for r in results)
        # 命中后 access_count 应 >= 1
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT access_count FROM memories WHERE id = ?", (m.id,))
        assert cur.fetchone()[0] >= 1


class TestMemoryManagerV3:
    def test_get_context_includes_core(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=None)
        mgr.core.set("user_profile", "用户偏好 Go")
        ctx = mgr.get_context_for_query("项目用什么语言")
        assert "用户偏好 Go" in ctx
        assert "## 核心记忆" in ctx

    def test_register_tools_returns_list(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=None)
        tools = mgr.get_tools()
        names = {t.name for t in tools}
        assert "core_memory_append" in names
        assert "core_memory_replace" in names


class TestReflector:
    @pytest.mark.asyncio
    async def test_parse_ops_from_response(self):
        from tars.memory.reflector import Reflector
        text = '[{"op": "update_core", "block": "user_profile", "action": "append", "old": "", "new": "用户偏好 Go"}, {"op": "archive", "content": "项目用 Python 3.14", "category": "fact", "importance": 0.7, "source": "conversation"}]'
        ops = Reflector._parse_ops(text)
        assert len(ops) == 2
        assert ops[0]["op"] == "update_core"
        assert ops[1]["op"] == "archive"

    @pytest.mark.asyncio
    async def test_parse_handles_code_block(self):
        from tars.memory.reflector import Reflector
        text = '```json\n[{"op": "noop"}]\n```'
        ops = Reflector._parse_ops(text)
        assert ops == [{"op": "noop"}]

    @pytest.mark.asyncio
    async def test_parse_handles_garbage(self):
        from tars.memory.reflector import Reflector
        ops = Reflector._parse_ops("not json at all")
        assert ops == []

    @pytest.mark.asyncio
    async def test_apply_update_core(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        from tars.memory.archival import ArchivalManager
        from tars.memory.reflector import Reflector
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        am = ArchivalManager(db)
        reflector = Reflector(provider=None, core=cm, archival=am)
        cm.set("user_profile", "")
        await reflector._apply_op({"op": "update_core", "block": "user_profile", "action": "append", "new": "用户偏好 Go"})
        assert "Go" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_apply_archive(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        from tars.memory.archival import ArchivalManager
        from tars.memory.reflector import Reflector
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        am = ArchivalManager(db)
        reflector = Reflector(provider=None, core=cm, archival=am)
        await reflector._apply_op({"op": "archive", "content": "用户使用 Mac M1", "category": "fact", "importance": 0.7, "source": "conversation"})
        recents = db.get_recent_memories(5)
        assert any("Mac M1" in m.content for m in recents)


class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_reflect_updates_core_via_mock_provider(self, tmp_path):
        """模拟 LLM 返回 update_core op，验证 core memory 被更新"""
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        from tars.models.base import ModelResponse

        class MockProvider:
            async def chat(self, messages, stream=False, temperature=0.7, **kwargs):
                resp = ModelResponse(
                    content='[{"op":"update_core","block":"user_profile","action":"append","old":"","new":"用户偏好 Go 后端"}]',
                    model="mock",
                    usage={},
                )
                return resp

        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=MockProvider())
        mgr.core.set("user_profile", "")
        await mgr.reflect("我喜欢用 Go 写后端", "好的，我记住了")
        assert "Go 后端" in mgr.core.get("user_profile")

    @pytest.mark.asyncio
    async def test_reflect_archives_web_knowledge(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        from tars.models.base import ModelResponse

        class MockProvider:
            async def chat(self, messages, stream=False, temperature=0.7, **kwargs):
                return ModelResponse(
                    content='[{"op":"archive","content":"FastAPI 用 Pydantic v2 验证","category":"domain_knowledge","importance":0.7,"source":"web"}]',
                    model="mock",
                    usage={},
                )

        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=MockProvider())
        await mgr.reflect("FastAPI 怎么验证参数", "用 Pydantic v2", used_web=True)
        recents = db.get_recent_memories(5)
        assert any("Pydantic" in m.content for m in recents)
