"""TARS 记忆系统 v2 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio


class TestRegexExtractor:
    def test_extract_chinese_preference(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("我喜欢使用Python编程，因为它简洁优雅。")
        assert len(result) >= 1
        assert "我喜欢使用Python编程" in result[0]["content"]
        assert result[0]["category"] == "user_preference"

    def test_extract_english_preference(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("I prefer dark mode for all my editors.")
        assert len(result) >= 1
        assert "dark mode" in result[0]["content"]

    def test_extract_decision(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("我们决定采用微服务架构来重构后端。")
        assert len(result) >= 1
        assert "微服务" in result[0]["content"]

    def test_extract_project_record(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("完成了用户认证模块的开发和测试。")
        assert len(result) >= 1
        assert "用户认证" in result[0]["content"]

    def test_no_extraction_from_empty(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("")
        assert result == []

    def test_no_extraction_from_irrelevant(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("今天天气不错。")
        assert result == []

    def test_short_content_filtered(self):
        from tars.memory.extractor import RegexExtractor
        ext = RegexExtractor()
        result = ext.extract("我喜欢它。")
        # "我喜欢它" 只有 4 字符，应被过滤（< 5）
        assert all(len(r["content"]) > 5 for r in result)


class TestLLMExtractor:
    def test_parse_valid_json(self):
        from tars.memory.extractor import LLMMemoryExtractor
        ext = LLMMemoryExtractor()
        result = ext._parse_response('[{"content": "用户喜欢Python", "category": "user_preference"}]')
        assert len(result) == 1
        assert result[0]["content"] == "用户喜欢Python"

    def test_parse_json_in_code_block(self):
        from tars.memory.extractor import LLMMemoryExtractor
        ext = LLMMemoryExtractor()
        text = '```json\n[{"content": "决定用Vue3", "category": "important_decision"}]\n```'
        result = ext._parse_response(text)
        assert len(result) == 1

    def test_parse_empty_array(self):
        from tars.memory.extractor import LLMMemoryExtractor
        ext = LLMMemoryExtractor()
        result = ext._parse_response("[]")
        assert result == []

    def test_parse_invalid_json(self):
        from tars.memory.extractor import LLMMemoryExtractor
        ext = LLMMemoryExtractor()
        result = ext._parse_response("这不是JSON")
        assert result == []


class TestDeduplicator:
    def test_exact_duplicate(self):
        from tars.memory.deduplicator import MemoryDeduplicator
        from tars.database.base import Memory
        from datetime import datetime

        dedup = MemoryDeduplicator()
        existing = [Memory(id="1", content="我喜欢Python", category="user_preference", created_at=datetime.now(), updated_at=datetime.now())]
        is_dup, target = dedup.is_duplicate("我喜欢Python", existing)
        assert is_dup is True
        assert target is None

    def test_contained_in_existing(self):
        from tars.memory.deduplicator import MemoryDeduplicator
        from tars.database.base import Memory
        from datetime import datetime

        dedup = MemoryDeduplicator()
        existing = [Memory(id="1", content="我喜欢使用Python编程", category="user_preference", created_at=datetime.now(), updated_at=datetime.now())]
        is_dup, target = dedup.is_duplicate("Python", existing)
        assert is_dup is True

    def test_new_is_more_complete(self):
        from tars.memory.deduplicator import MemoryDeduplicator
        from tars.database.base import Memory
        from datetime import datetime

        dedup = MemoryDeduplicator()
        existing = [Memory(id="1", content="使用Python", category="user_preference", created_at=datetime.now(), updated_at=datetime.now())]
        # 新的完全包含旧的
        is_dup, target = dedup.is_duplicate("我喜欢使用Python编程", existing)
        assert is_dup is True
        assert target is not None  # 应该更新旧记忆

    def test_not_duplicate(self):
        from tars.memory.deduplicator import MemoryDeduplicator
        from tars.database.base import Memory
        from datetime import datetime

        dedup = MemoryDeduplicator()
        existing = [Memory(id="1", content="我喜欢Python", category="user_preference", created_at=datetime.now(), updated_at=datetime.now())]
        is_dup, target = dedup.is_duplicate("项目使用了Docker部署", existing)
        assert is_dup is False


class TestEmbeddings:
    def test_local_embedding_encode(self):
        from tars.memory.embeddings import LocalEmbeddingProvider
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
        vecs = provider.encode(["你好世界", "Hello World"])
        assert len(vecs) == 2
        assert len(vecs[0]) == 512  # bge-small 维度
        assert all(isinstance(v, float) for v in vecs[0])

    def test_similar_texts_have_high_similarity(self):
        from tars.memory.embeddings import LocalEmbeddingProvider
        from tars.memory.deduplicator import cosine_similarity
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
        vecs = provider.encode(["我喜欢用Python编程", "我偏好Python开发"])
        sim = cosine_similarity(vecs[0], vecs[1])
        assert sim > 0.7

    def test_different_texts_have_low_similarity(self):
        from tars.memory.embeddings import LocalEmbeddingProvider
        from tars.memory.deduplicator import cosine_similarity
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
        vecs = provider.encode(["我喜欢用Python编程", "今天天气很好适合出门"])
        sim = cosine_similarity(vecs[0], vecs[1])
        assert sim < 0.5

    def test_serialize_deserialize(self):
        from tars.memory.embeddings import serialize_vector, deserialize_vector
        vec = [0.1, 0.2, 0.3, -0.5, 1.0]
        blob = serialize_vector(vec)
        restored = deserialize_vector(blob)
        assert len(restored) == 5
        assert abs(restored[0] - 0.1) < 1e-6


class TestHybridSearch:
    @pytest.fixture
    def setup_db(self, tmp_path):
        from tars.database.base import Database
        from tars.memory.embeddings import LocalEmbeddingProvider, serialize_vector
        db = Database(db_path=str(tmp_path / "test.db"))
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")

        memories_data = [
            ("我喜欢使用Python编程", "user_preference"),
            ("项目采用了Vue3前端框架", "project_record"),
            ("决定使用Docker部署服务", "important_decision"),
        ]
        for content, category in memories_data:
            vec = provider.encode([content])[0]
            db.add_memory(content=content, category=category, embedding=serialize_vector(vec))

        return db, provider

    def test_semantic_search_finds_related(self, setup_db):
        from tars.memory.search import HybridSearch
        db, provider = setup_db
        search = HybridSearch(db, provider)
        results = search.search("Python 开发", limit=3)
        assert len(results) > 0
        assert any("Python" in m.content for m in results)

    def test_keyword_search_works(self, setup_db):
        from tars.memory.search import HybridSearch
        db, provider = setup_db
        search = HybridSearch(db, provider)
        results = search.search("Docker", limit=3)
        assert any("Docker" in m.content for m in results)


class TestMemoryManagerIntegration:
    @pytest.fixture
    def manager(self, tmp_path):
        from tars.database.base import Database
        from tars.memory import MemoryManager, LocalEmbeddingProvider
        db = Database(db_path=str(tmp_path / "test.db"))
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
        return MemoryManager(db=db, embedding_provider=provider)

    @pytest.mark.asyncio
    async def test_archival_insert_saves_memory(self, manager):
        """通过 archival 直接写入记忆"""
        mem = await manager.add_manual_memory("我喜欢使用TypeScript开发前端项目", category="preference")
        assert mem is not None
        assert "TypeScript" in mem.content

    @pytest.mark.asyncio
    async def test_dedup_prevents_duplicate(self, manager):
        """重复内容不会被保存两次"""
        await manager.add_manual_memory("我喜欢使用Python编程语言", category="preference")
        result2 = await manager.add_manual_memory("我喜欢使用Python编程语言", category="preference")
        assert result2 is None

    @pytest.mark.asyncio
    async def test_get_context_for_query(self, manager):
        """搜索返回相关记忆上下文"""
        await manager.add_manual_memory("我喜欢使用Python编程", category="preference")
        context = manager.get_context_for_query("Python")
        assert "Python" in context
        assert "相关长期记忆" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
