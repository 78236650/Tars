"""向量搜索与知识库系统功能测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os


class TestDocumentChunker:
    """文档分块器测试"""

    def test_fixed_length_chunk(self):
        from tars.knowledge.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10, strategy="fixed")
        text = "a" * 120
        chunks = chunker.chunk(text)
        assert len(chunks) > 1
        assert all(len(c["text"]) <= 50 for c in chunks)

    def test_paragraph_chunk(self):
        from tars.knowledge.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=100, strategy="paragraph")
        text = "段落一。\n\n段落二。\n\n段落三。"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        assert "段落一" in chunks[0]["text"]

    def test_recursive_chunk(self):
        from tars.knowledge.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=50, strategy="recursive")
        text = "第一句。第二句非常长，包含很多内容需要被分割。\n\n第三句。"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        assert all(len(c["text"]) <= 100 for c in chunks)  # 递归分块后不应超过合理长度

    def test_chunk_metadata(self):
        from tars.knowledge.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=50, strategy="fixed")
        chunks = chunker.chunk("hello world", metadata={"file": "test.txt"})
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["file"] == "test.txt"
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["chunk_total"] == 1

    def test_empty_text(self):
        from tars.knowledge.chunker import DocumentChunker
        chunker = DocumentChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []


class TestSearchCache:
    """搜索缓存测试"""

    def test_cache_set_get(self, tmp_path):
        from tars.database import Database
        from tars.search.cache import SearchCache
        db = Database(db_path=str(tmp_path / "test.db"))
        cache = SearchCache(db)

        cache.set("test query", [{"id": "1", "text": "result"}], "memory", 5, 300)
        result = cache.get("test query", "memory", 5)
        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_cache_expiration(self, tmp_path):
        from tars.database import Database
        from tars.search.cache import SearchCache
        import time
        db = Database(db_path=str(tmp_path / "test.db"))
        cache = SearchCache(db)

        cache.set("expire query", [{"id": "1"}], "memory", 5, ttl_seconds=1)
        time.sleep(1.1)
        result = cache.get("expire query", "memory", 5)
        assert result is None

    def test_cache_clear(self, tmp_path):
        from tars.database import Database
        from tars.search.cache import SearchCache
        db = Database(db_path=str(tmp_path / "test.db"))
        cache = SearchCache(db)

        cache.set("q1", [{"id": "1"}], "memory", 5)
        cache.set("q2", [{"id": "2"}], "web", 5)
        count = cache.clear("memory")
        assert count >= 1
        assert cache.get("q1", "memory", 5) is None

    def test_cache_cleanup_expired(self, tmp_path):
        from tars.database import Database
        from tars.search.cache import SearchCache
        import time
        db = Database(db_path=str(tmp_path / "test.db"))
        cache = SearchCache(db)

        cache.set("old", [{"id": "1"}], "memory", 5, ttl_seconds=1)
        time.sleep(1.1)
        count = cache.cleanup_expired()
        assert count >= 1


class TestQueryExpansion:
    """查询扩展测试"""

    def test_synonym_expand(self):
        from tars.search.query_expansion import QueryExpander
        expander = QueryExpander()
        queries = expander.expand("怎么安装软件", method="synonym")
        assert len(queries) >= 2
        assert "怎么安装软件" in queries
        # 应该包含同义词替换后的查询
        assert any("如何" in q for q in queries)

    def test_no_expansion_for_empty(self):
        from tars.search.query_expansion import QueryExpander
        expander = QueryExpander()
        assert expander.expand("", method="synonym") == []

    def test_expand_without_provider(self):
        from tars.search.query_expansion import QueryExpander
        expander = QueryExpander(provider=None)
        queries = expander.expand("测试查询", method="llm")
        # 没有 provider 时 LLM 扩展应该返回空
        assert len(queries) == 1  # 只有原始查询


class TestCrossEncoderReranker:
    """Cross-Encoder 重排序测试"""

    def test_rerank_without_model(self):
        from tars.reranker.cross_encoder import CrossEncoderReranker
        reranker = CrossEncoderReranker()
        # 模型未加载时应该按原始分数排序
        docs = [
            {"text": "doc1", "score": 0.3},
            {"text": "doc2", "score": 0.8},
            {"text": "doc3", "score": 0.5},
        ]
        result = reranker.rerank("query", docs, top_k=2)
        assert len(result) == 2
        assert result[0]["score"] == 0.8  # 按原始分数排序

    def test_rerank_empty_docs(self):
        from tars.reranker.cross_encoder import CrossEncoderReranker
        reranker = CrossEncoderReranker()
        assert reranker.rerank("query", []) == []


class TestChromaVectorStore:
    """Chroma 向量数据库测试"""

    def test_init_without_chroma(self):
        from tars.vectorstore import ChromaVectorStore
        vs = ChromaVectorStore(persist_directory="/tmp/test_chroma")
        # 即使 chromadb 未安装，初始化也不应报错
        assert not vs.is_available

    def test_add_and_query_mock(self, tmp_path, monkeypatch):
        """使用 mock 测试 add/query 逻辑"""
        from tars.vectorstore import ChromaVectorStore

        # Mock chromadb
        class MockCollection:
            def __init__(self):
                self.data = {}
            def add(self, **kwargs):
                for i, doc_id in enumerate(kwargs["ids"]):
                    self.data[doc_id] = {
                        "document": kwargs["documents"][i],
                        "metadata": kwargs["metadatas"][i],
                        "embedding": kwargs.get("embeddings", [None])[i],
                    }
            def query(self, **kwargs):
                return {
                    "ids": [["id1"]],
                    "documents": [["test doc"]],
                    "metadatas": [[{"key": "val"}]],
                    "distances": [[0.1]],
                }

        class MockClient:
            def get_collection(self, name):
                raise Exception("not found")
            def create_collection(self, name, metadata=None):
                return MockCollection()

        vs = ChromaVectorStore(persist_directory=str(tmp_path))
        vs._client = MockClient()

        # 测试 add_documents
        ids = vs.add_documents(
            documents=["test doc"],
            metadatas=[{"key": "val"}],
            ids=["id1"],
            tenant_id="default",
            collection_name="memories",
        )
        assert ids == ["id1"]

        # 测试 query
        results = vs.query("test", top_k=1, tenant_id="default", collection_name="memories")
        assert len(results) == 1
        assert results[0]["id"] == "id1"
        assert results[0]["document"] == "test doc"

    def test_count(self, tmp_path, monkeypatch):
        from tars.vectorstore import ChromaVectorStore

        class MockCollection:
            def count(self):
                return 5

        class MockClient:
            def get_collection(self, name):
                return MockCollection()
            def create_collection(self, name, metadata=None):
                return MockCollection()

        vs = ChromaVectorStore(persist_directory=str(tmp_path))
        vs._client = MockClient()
        assert vs.count("default", "memories") == 5


class TestKnowledgeIndexer:
    """知识库索引器测试"""

    def test_index_document_mock(self, tmp_path, monkeypatch):
        from tars.knowledge.indexer import KnowledgeIndexer

        # Mock vector_store
        class MockVectorStore:
            def __init__(self):
                self.docs = []
            def add_documents(self, **kwargs):
                self.docs.extend(kwargs["documents"])
            def is_available(self):
                return True

        mock_vs = MockVectorStore()
        indexer = KnowledgeIndexer(mock_vs, embedding_provider=None, chunk_size=50)

        result = indexer.index_document(
            text="这是测试文档。包含多句话。用于测试分块和索引功能。",
            doc_id="doc1",
            collection_id="coll1",
            file_name="test.txt",
        )
        assert result["status"] == "indexed"
        assert result["chunk_count"] > 0
        assert result["doc_id"] == "doc1"

    def test_index_empty_document(self, tmp_path):
        from tars.knowledge.indexer import KnowledgeIndexer

        class MockVectorStore:
            def is_available(self):
                return True

        indexer = KnowledgeIndexer(MockVectorStore(), embedding_provider=None)
        result = indexer.index_document("", "doc1", "coll1")
        assert result["status"] == "empty"
        assert result["chunk_count"] == 0

    def test_delete_document_removes_chunks_and_db_record(self, tmp_path):
        from tars.database import Database
        from tars.knowledge.indexer import KnowledgeIndexer

        class MockCollection:
            def __init__(self):
                self.deleted_where = None

            def delete(self, where=None):
                self.deleted_where = where

        class MockVectorStore:
            def __init__(self):
                self.collection = MockCollection()

            @property
            def is_available(self):
                return True

            def get_collection(self, collection_name, tenant_id="default"):
                assert collection_name == "knowledge_coll1"
                return self.collection

        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc1", "coll1", "a.txt", "/tmp/a.txt", "text/plain", 3, "indexed", "2026-05-16T00:00:00"),
        )
        conn.commit()

        vector_store = MockVectorStore()
        indexer = KnowledgeIndexer(vector_store, embedding_provider=None, db=db)

        assert indexer.delete_document("doc1", "coll1") is True
        assert vector_store.collection.deleted_where == {"doc_id": "doc1"}

        cursor.execute("SELECT id FROM document_files WHERE id = ?", ("doc1",))
        assert cursor.fetchone() is None

    def test_index_document_sqlite_fallback_when_chroma_unavailable(self, tmp_path):
        from tars.database import Database
        from tars.knowledge.indexer import KnowledgeIndexer
        from tars.memory.embeddings import DeterministicEmbeddingProvider

        class UnavailableVectorStore:
            @property
            def is_available(self):
                return False

        db = Database(db_path=str(tmp_path / "sqlite_kb.db"))
        indexer = KnowledgeIndexer(
            UnavailableVectorStore(),
            DeterministicEmbeddingProvider(dim=64),
            db=db,
            chunk_size=80,
        )
        result = indexer.index_document(
            text="SQLite 回退索引测试。包含足够长度用于分块。",
            doc_id="doc-sqlite",
            collection_id="coll-sqlite",
            file_name="note.txt",
            tenant_id="default",
        )
        assert result["status"] == "indexed"
        assert result.get("backend") == "sqlite"
        assert result["chunk_count"] > 0

        from tars.knowledge.sqlite_store import search_chunks

        hits = search_chunks(
            db,
            DeterministicEmbeddingProvider(dim=64),
            query="SQLite",
            collection_ids=["coll-sqlite"],
            tenant_id="default",
            top_k=3,
        )
        assert len(hits) >= 1

    def test_index_file_uses_document_parser_for_markdown(self, tmp_path):
        from tars.knowledge.indexer import KnowledgeIndexer

        class MockVectorStore:
            def add_documents(self, **kwargs):
                return kwargs["ids"]

            @property
            def is_available(self):
                return True

        file_path = tmp_path / "guide.md"
        file_path.write_text("# 标题\n\n- 第一项\n- 第二项", encoding="utf-8")

        indexer = KnowledgeIndexer(MockVectorStore(), embedding_provider=None, chunk_size=500)
        result = indexer.index_file(str(file_path), "doc-md", "coll1")

        assert result["status"] == "indexed"
        assert result["chunk_count"] >= 1


class TestKnowledgeRetriever:
    """知识库检索器测试"""

    def test_retrieve_mock(self, monkeypatch):
        from tars.knowledge.retriever import KnowledgeRetriever

        class MockVectorStore:
            def query(self, **kwargs):
                return [
                    {"document": "result1", "metadata": {"file_name": "a.txt"}, "distance": 0.1},
                    {"document": "result2", "metadata": {"file_name": "b.txt"}, "distance": 0.2},
                ]

        retriever = KnowledgeRetriever(MockVectorStore())
        results = retriever.retrieve("query", ["coll1"], top_k=2)
        assert len(results) == 2
        assert results[0]["score"] > results[1]["score"]  # 距离小的分数高

    def test_retrieve_empty_collections(self):
        from tars.knowledge.retriever import KnowledgeRetriever
        retriever = KnowledgeRetriever(None)
        assert retriever.retrieve("query", []) == []

    def test_retrieve_with_query_expansion_deduplicates_by_best_score(self):
        from tars.knowledge.retriever import KnowledgeRetriever

        class MockVectorStore:
            def query(self, **kwargs):
                query = kwargs["query_text"]
                if query == "原始问题":
                    return [
                        {
                            "id": "doc1_chunk_0",
                            "document": "结果 A",
                            "metadata": {"file_name": "a.txt", "doc_id": "doc1"},
                            "distance": 0.4,
                        }
                    ]
                return [
                    {
                        "id": "doc1_chunk_0",
                        "document": "结果 A",
                        "metadata": {"file_name": "a.txt", "doc_id": "doc1"},
                        "distance": 0.1,
                    }
                ]

        class StubExpander:
            def expand(self, query, method="synonym"):
                return [query, "扩展问题"]

        retriever = KnowledgeRetriever(MockVectorStore(), query_expander=StubExpander())
        results = retriever.retrieve("原始问题", ["coll1"], top_k=3, expand=True)

        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(0.9)


class TestSearchGateway:
    """统一搜索网关测试"""

    def test_search_with_mock_memory(self, tmp_path, monkeypatch):
        from tars.search.gateway import SearchGateway
        from tars.database import Database

        db = Database(db_path=str(tmp_path / "test.db"))

        # Mock memory_search
        class MockMemorySearch:
            def search(self, query, limit=5):
                return []

        gateway = SearchGateway(
            db=db,
            vector_store=None,
            embedding_provider=None,
            memory_search=MockMemorySearch(),
        )

        result = gateway.search("test", sources=["memory"], limit=5, use_expansion=False)
        assert "memory" in result["sources"]

    def test_search_cache_hit(self, tmp_path, monkeypatch):
        from tars.search.gateway import SearchGateway
        from tars.database import Database

        db = Database(db_path=str(tmp_path / "test.db"))
        gateway = SearchGateway(db, None, None)

        # 预置缓存
        gateway.cache.set("cached query", [{"id": "1", "content": "cached"}], "memory", 5)

        result = gateway.search("cached query", sources=["memory"], use_expansion=False, use_cache=True)
        assert len(result["sources"]["memory"]) == 1
        assert result["sources"]["memory"][0]["content"] == "cached"

    def test_search_gateway_reranks_memory_results(self, tmp_path):
        from tars.search.gateway import SearchGateway
        from tars.database import Database

        class MockMemorySearch:
            def search(self, query, limit=5):
                return []

        class StubReranker:
            def rerank(self, query, documents, top_k=5, text_key="content"):
                return list(reversed(documents))[:top_k]

        db = Database(db_path=str(tmp_path / "test.db"))
        gateway = SearchGateway(
            db=db,
            vector_store=None,
            embedding_provider=None,
            memory_search=MockMemorySearch(),
            reranker=StubReranker(),
        )
        gateway.cache.set(
            "cached query",
            [
                {"id": "1", "content": "first", "score": 0.2},
                {"id": "2", "content": "second", "score": 0.1},
            ],
            "memory",
            5,
        )

        result = gateway.search("cached query", sources=["memory"], use_expansion=False, use_cache=True)
        assert result["sources"]["memory"][0]["id"] == "2"


class TestKnowledgeApiUpgrade:
    def test_batch_upload_indexes_success_and_failure(self, tmp_path, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from tars.api.knowledge import router, init_knowledge_api
        from tars.database import Database

        class StubVectorStore:
            @property
            def is_available(self):
                return False

            def add_documents(self, **kwargs):
                return kwargs["ids"]

        db = Database(db_path=str(tmp_path / "test.db"))
        from tars.org import ORG_ID
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO document_collections (id, tenant_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("coll1", ORG_ID, "知识库", "", "2026-05-16T00:00:00", "2026-05-16T00:00:00"),
        )
        conn.commit()

        app = FastAPI()
        app.include_router(router)
        init_knowledge_api(db, StubVectorStore(), None)
        from tests.conftest import setup_knowledge_auth
        auth_headers, _user = setup_knowledge_auth(db)
        client = TestClient(app)

        response = client.post(
            "/api/knowledge/collections/coll1/batch",
            files=[
                ("files", ("good.txt", b"hello world", "text/plain")),
                ("files", ("bad.bin", b"\xff\xfe\x00", "application/octet-stream")),
            ],
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        assert payload["indexed"] == 1
        assert payload["failed"][0]["file"] == "bad.bin"


class TestDatabaseSchema:
    """数据库 Schema 测试"""

    def test_document_collections_table(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_collections'")
        assert cursor.fetchone() is not None

    def test_document_files_table(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_files'")
        assert cursor.fetchone() is not None

    def test_search_cache_table(self, tmp_path):
        from tars.database import Database
        from tars.search.cache import SearchCache
        db = Database(db_path=str(tmp_path / "test.db"))
        SearchCache(db)  # 缓存表由 SearchCache 初始化时创建
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_cache'")
        assert cursor.fetchone() is not None


class TestIntegration:
    """集成测试"""

    def test_end_to_end_chunk_index_retrieve(self, tmp_path, monkeypatch):
        """端到端：分块 → 索引 → 检索"""
        from tars.knowledge.chunker import DocumentChunker
        from tars.knowledge.indexer import KnowledgeIndexer
        from tars.knowledge.retriever import KnowledgeRetriever

        # Mock vector store
        class MockVS:
            def __init__(self):
                self.storage = {}
            def add_documents(self, **kwargs):
                for i, doc_id in enumerate(kwargs["ids"]):
                    self.storage[doc_id] = {
                        "document": kwargs["documents"][i],
                        "metadata": kwargs["metadatas"][i],
                    }
            def query(self, **kwargs):
                results = []
                for doc_id, data in self.storage.items():
                    if kwargs.get("collection_name", "") in doc_id or True:
                        results.append({
                            "id": doc_id,
                            "document": data["document"],
                            "metadata": data["metadata"],
                            "distance": 0.1,
                        })
                return results[:kwargs.get("top_k", 5)]
            @property
            def is_available(self):
                return True

        mock_vs = MockVS()

        # 1. 分块
        chunker = DocumentChunker(chunk_size=100, strategy="recursive")
        text = "TARS 是一个 AI Agent 框架。\n\n它支持多种工具调用。\n\n支持记忆系统。"
        chunks = chunker.chunk(text, metadata={"file_name": "intro.txt"})
        assert len(chunks) > 0

        # 2. 索引
        indexer = KnowledgeIndexer(mock_vs, embedding_provider=None, chunk_size=100)
        result = indexer.index_document(text, "doc1", "coll1", "intro.txt")
        assert result["status"] == "indexed"
        assert result["chunk_count"] > 0

        # 3. 检索
        retriever = KnowledgeRetriever(mock_vs)
        results = retriever.retrieve("TARS 框架", ["coll1"], top_k=3)
        assert len(results) > 0

    def test_memory_with_chroma_fallback(self, tmp_path, monkeypatch):
        """测试 Chroma 失败时回退到 SQLite"""
        from tars.database import Database
        from tars.memory.search import HybridSearch

        db = Database(db_path=str(tmp_path / "test.db"))

        # Mock 不可用的 vector_store
        class MockVS:
            @property
            def is_available(self):
                return False

        search = HybridSearch(db, embedding_provider=None, vector_store=MockVS())
        results = search.search("test query", limit=5)
        # 即使 Chroma 不可用，也不应报错
        assert isinstance(results, list)
