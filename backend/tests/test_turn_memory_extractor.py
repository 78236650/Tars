"""Tests for chat turn memory extraction."""
from tars.memory.extractor import HeuristicTurnExtractor, LLMMemoryExtractor, TURN_EXTRACTION_PROMPT
from tars.memory.manager import MemoryManager


class TestHeuristicTurnExtractor:
    def test_extracts_markdown_bullets_from_technical_reply(self):
        assistant = """## 修复方案
- SQLSecurityChecker 只对 SELECT 追加 LIMIT
- SHOW TABLES 等元数据语句不应追加 LIMIT

请重启后端后再试。"""
        items = HeuristicTurnExtractor().extract("为什么 show tables 报错", assistant)
        assert len(items) >= 2
        assert any("LIMIT" in item["content"] for item in items)

    def test_extracts_paragraph_when_no_bullets(self):
        assistant = (
            "根因是查询页只在首次加载时拉取数据源列表，切换到 SQL 查询时不会刷新，"
            "因此新建的数据源不会出现在下拉框中。"
        )
        items = HeuristicTurnExtractor().extract("选不了新建数据库", assistant)
        assert len(items) >= 1
        assert "数据源" in items[0]["content"]


class TestExtractTurnMemories:
    def test_heuristic_fallback_without_provider(self, tmp_path):
        from tars.database import Database

        db = Database(db_path=str(tmp_path / "mem.db"))
        manager = MemoryManager(db=db, provider=None)
        assistant = """## 结论
- MySQL 的 SHOW TABLES 不支持 LIMIT 后缀
- 仅 SELECT/WITH 才自动追加 LIMIT 1000"""
        items = __import__("asyncio").run(
            manager.extract_turn_memories("show tables 报错", assistant)
        )
        assert len(items) >= 1
        assert items[0]["category"] in {"fact", "domain_knowledge", "decision", "preference"}


class TestTurnExtractionPrompt:
    def test_prompt_mentions_technical_points(self):
        assert "技术要点" in TURN_EXTRACTION_PROMPT
        assert "domain_knowledge" in TURN_EXTRACTION_PROMPT
