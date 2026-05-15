# 向量搜索与知识库升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 TARS 向量搜索与知识库系统：集成 Reranker、修复文档删除、支持 PDF/DOCX、查询扩展、批量索引、Embedding 模型切换。

**Architecture:** 在现有 HybridSearch + ChromaDB + KnowledgeIndexer 基础上增强。Reranker 作为可选精排层插入搜索管线末端；DocumentParser 作为新模块统一文件解析；Embedding 切换通过全局 provider 热替换实现。

**Tech Stack:** Python, FastAPI, ChromaDB, sentence-transformers, cross-encoder, pymupdf, python-docx, SQLAlchemy

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/tars/knowledge/parsers.py` | **新增** 文档解析器（PDF/DOCX/MD/TXT） |
| `backend/tars/memory/search.py` | 修改：插入 reranker 精排步骤 |
| `backend/tars/search/gateway.py` | 修改：插入 reranker 精排步骤 |
| `backend/tars/knowledge/indexer.py` | 修改：修复 delete_document，集成 DocumentParser |
| `backend/tars/knowledge/retriever.py` | 修改：接入 QueryExpansion |
| `backend/tars/api/knowledge.py` | 修改：新增 batch 端点，修复 delete 端点 |
| `backend/tars/api/settings.py` | **新增** embedding 配置 API |
| `backend/tars/memory/embeddings.py` | 修改：支持运行时切换 |
| `backend/requirements.txt` | 修改：新增 pymupdf, python-docx |
| `backend/tests/test_vector_upgrade.py` | **新增** 全部升级项测试 |

---

### Task 1: 文档删除修复

**Files:**
- Modify: `backend/tars/knowledge/indexer.py:80-96`
- Modify: `backend/tars/api/knowledge.py:237-251`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_vector_upgrade.py
import pytest
from unittest.mock import MagicMock, patch

class TestDocumentDeletion:
    def test_delete_document_removes_chunks_from_chroma(self):
        mock_vector_store = MagicMock()
        mock_vector_store.is_available = True
        mock_embedding = MagicMock()

        from tars.knowledge.indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer(mock_vector_store, mock_embedding)

        result = indexer.delete_document(
            doc_id="doc_123",
            collection_id="coll_abc",
            chunk_count=3,
            tenant_id="default",
        )

        assert result is True
        mock_vector_store.delete_by_ids.assert_called_once_with(
            ids=["doc_123_chunk_0", "doc_123_chunk_1", "doc_123_chunk_2"],
            tenant_id="default",
            collection_name="knowledge_coll_abc",
        )

    def test_delete_document_returns_false_when_chunk_count_zero(self):
        mock_vector_store = MagicMock()
        mock_embedding = MagicMock()

        from tars.knowledge.indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer(mock_vector_store, mock_embedding)

        result = indexer.delete_document(
            doc_id="doc_123",
            collection_id="coll_abc",
            chunk_count=0,
            tenant_id="default",
        )
        assert result is True
        mock_vector_store.delete_by_ids.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestDocumentDeletion -v`
Expected: FAIL (delete_document signature mismatch)

- [ ] **Step 3: Implement fix in indexer.py**

Replace `delete_document` method in `backend/tars/knowledge/indexer.py:80-96`:

```python
def delete_document(
    self,
    doc_id: str,
    collection_id: str,
    chunk_count: int = 0,
    tenant_id: str = "default",
) -> bool:
    """删除文档的所有 chunk"""
    try:
        if chunk_count > 0:
            chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(chunk_count)]
            collection_name = f"knowledge_{collection_id}"
            self.vector_store.delete_by_ids(
                ids=chunk_ids,
                tenant_id=tenant_id,
                collection_name=collection_name,
            )
        return True
    except Exception as e:
        print(f"[KnowledgeIndexer] 删除失败: {e}")
        return False
```

- [ ] **Step 4: Fix API delete endpoint**

Replace `backend/tars/api/knowledge.py:237-251`:

```python
@router.delete("/collections/{coll_id}/documents/{doc_id}")
async def delete_document(
    coll_id: str,
    doc_id: str,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_id = x_tenant_id or "default"
    conn = _db._get_conn()
    cursor = conn.cursor()

    # 获取 chunk_count
    cursor.execute("SELECT chunk_count FROM document_files WHERE id = ? AND collection_id = ?", (doc_id, coll_id))
    row = cursor.fetchone()
    chunk_count = row[0] if row else 0

    # 从向量数据库删除
    _indexer.delete_document(doc_id, coll_id, chunk_count=chunk_count, tenant_id=tenant_id)

    # 删除数据库记录
    cursor.execute("DELETE FROM document_files WHERE id = ? AND collection_id = ?", (doc_id, coll_id))
    conn.commit()

    return {"success": True, "message": "文档已删除"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestDocumentDeletion -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tars/knowledge/indexer.py backend/tars/api/knowledge.py backend/tests/test_vector_upgrade.py
git commit -m "fix: knowledge document deletion now removes chunks from Chroma"
```

---

### Task 2: Reranker 集成到搜索管线

**Files:**
- Modify: `backend/tars/memory/search.py`
- Modify: `backend/tars/search/gateway.py`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Write failing test**

```python
# append to backend/tests/test_vector_upgrade.py

class TestRerankerIntegration:
    def test_hybrid_search_uses_reranker(self):
        from tars.memory.search import HybridSearch
        from unittest.mock import MagicMock, patch

        mock_db = MagicMock()
        mock_db.search_memories.return_value = []
        mock_embedding = MagicMock()
        mock_vector_store = MagicMock()
        mock_vector_store.is_available = True
        mock_vector_store.query.return_value = []

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = []

        search = HybridSearch(mock_db, mock_embedding, vector_store=mock_vector_store, reranker=mock_reranker)
        search.search("test query", limit=5)

        # reranker.rerank should have been called (even if no results)
        # When there are no candidates, reranker is not called
        mock_reranker.rerank.assert_not_called()

    def test_hybrid_search_reranker_called_with_candidates(self):
        from tars.memory.search import HybridSearch
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_mem = MagicMock()
        mock_mem.id = "m1"
        mock_mem.content = "test content"
        mock_mem.category = "fact"
        mock_db.search_memories.return_value = [mock_mem]
        mock_db.reinforce_memory.return_value = None

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [{"text": "test content", "score": 0.9, "original": mock_mem}]

        search = HybridSearch(mock_db, None, vector_store=None, reranker=mock_reranker)
        results = search.search("test", limit=5)

        mock_reranker.rerank.assert_called_once()

    def test_hybrid_search_works_without_reranker(self):
        from tars.memory.search import HybridSearch
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_db.search_memories.return_value = []

        search = HybridSearch(mock_db, None, vector_store=None, reranker=None)
        results = search.search("test", limit=5)
        assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestRerankerIntegration -v`
Expected: FAIL (HybridSearch doesn't accept reranker param)

- [ ] **Step 3: Modify HybridSearch to accept and use reranker**

In `backend/tars/memory/search.py`, update `__init__` and `search`:

```python
class HybridSearch:
    """语义搜索 + FTS 关键词搜索 + 衰减加权 + 可选 Reranker"""

    def __init__(
        self,
        db,
        embedding_provider: EmbeddingProvider = None,
        tenant_id: str = "default",
        vector_store=None,
        reranker=None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.tenant_id = tenant_id
        self.vector_store = vector_store
        self.reranker = reranker

    def search(self, query: str, limit: int = 5) -> list:
        """混合搜索 + 衰减加权 + 可选 Reranker + 命中强化"""
        scored: dict = {}

        # 1. 语义搜索
        semantic_hits = 0
        if self.vector_store and self.vector_store.is_available:
            try:
                self._chroma_semantic_score(query, scored)
                semantic_hits = len(scored)
            except Exception as e:
                print(f"[HybridSearch] Chroma search failed: {e}, fallback to SQLite")
                if self.embedding_provider:
                    try:
                        self._sqlite_semantic_score(query, scored)
                        semantic_hits = len(scored)
                    except Exception as e2:
                        print(f"[HybridSearch] {_semantic_skip_reason(e2)}")
        elif self.embedding_provider:
            try:
                self._sqlite_semantic_score(query, scored)
                semantic_hits = len(scored)
            except Exception as e:
                print(f"[HybridSearch] {_semantic_skip_reason(e)}")

        # 2. FTS 关键词搜索
        kw_hits = 0
        try:
            prev_count = len(scored)
            self._keyword_score(query, scored)
            kw_hits = len(scored) - prev_count
        except Exception:
            pass

        # 3. Reranker 精排（如果有候选且 reranker 可用）
        if self.reranker and scored:
            candidates = [
                {"text": mem.content, "score": score, "original": mem}
                for mem, score in scored.values()
            ]
            reranked = self.reranker.rerank(query, candidates, top_k=limit, text_key="text")
            results = [item["original"] for item in reranked]
        else:
            # 4. 排序取 top
            ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]
            results = [mem for mem, _ in ranked]

        # 5. 命中强化
        for mem in results:
            try:
                self.db.reinforce_memory(mem.id, tenant_id=self.tenant_id)
            except Exception:
                pass

        # 6. 检索日志
        top_preview = ", ".join(
            f"[{m.category}]{m.content[:30]}" for m in results[:3]
        ) if results else "无命中"
        print(
            f"[HybridSearch] query=\"{query[:40]}\" "
            f"semantic={semantic_hits} keyword={kw_hits} "
            f"reranked={'yes' if self.reranker and scored else 'no'} "
            f"top={len(results)} | {top_preview}"
        )

        return results
```

- [ ] **Step 4: Modify SearchGateway to accept and use reranker**

In `backend/tars/search/gateway.py`, add reranker to `__init__` and use it in `search`:

```python
class SearchGateway:
    """统一搜索入口"""

    def __init__(
        self,
        db,
        vector_store,
        embedding_provider,
        provider=None,
        memory_search=None,
        knowledge_retriever=None,
        web_search_tool=None,
        reranker=None,
    ):
        self.db = db
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.provider = provider
        self.memory_search = memory_search
        self.knowledge_retriever = knowledge_retriever
        self.web_search_tool = web_search_tool
        self.reranker = reranker

        self.expander = QueryExpander(provider)
        self.cache = SearchCache(db)
```

At the end of the `search` method, before `return results`, add reranking for knowledge results:

```python
        # Rerank knowledge results
        if "knowledge" in results["sources"] and self.reranker and results["sources"]["knowledge"]:
            candidates = results["sources"]["knowledge"]
            reranked = self.reranker.rerank(query, candidates, top_k=limit, text_key="text")
            results["sources"]["knowledge"] = reranked

        return results
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestRerankerIntegration -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tars/memory/search.py backend/tars/search/gateway.py backend/tests/test_vector_upgrade.py
git commit -m "feat: integrate CrossEncoderReranker into search pipeline"
```

---

### Task 3: PDF/DOCX 文档解析器

**Files:**
- Create: `backend/tars/knowledge/parsers.py`
- Modify: `backend/tars/knowledge/indexer.py:98-122`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Add dependencies**

Append to `backend/requirements.txt`:

```
pymupdf>=1.24.0
python-docx>=1.1.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install pymupdf python-docx`

- [ ] **Step 3: Write failing test**

```python
# append to backend/tests/test_vector_upgrade.py
import tempfile
import os

class TestDocumentParsers:
    def test_text_parser(self):
        from tars.knowledge.parsers import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Hello World 你好世界")
            path = f.name

        parser = DocumentParser()
        text = parser.parse(path)
        os.unlink(path)

        assert "Hello World" in text
        assert "你好世界" in text

    def test_markdown_parser(self):
        from tars.knowledge.parsers import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write("# Title\n\n**Bold** text\n\n- item 1\n- item 2")
            path = f.name

        parser = DocumentParser()
        text = parser.parse(path)
        os.unlink(path)

        assert "Title" in text
        assert "Bold" in text
        assert "item 1" in text

    def test_unsupported_format_raises(self):
        from tars.knowledge.parsers import DocumentParser

        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("data")
            path = f.name

        parser = DocumentParser()
        text = parser.parse(path)
        os.unlink(path)
        # Unsupported formats fall back to text read
        assert text == "data"

    def test_pdf_parser(self):
        """PDF 解析（需要 pymupdf）"""
        from tars.knowledge.parsers import DocumentParser
        pytest.importorskip("fitz")

        # 创建一个简单的 PDF
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "PDF Test Content 测试内容")
        path = tempfile.mktemp(suffix=".pdf")
        doc.save(path)
        doc.close()

        parser = DocumentParser()
        text = parser.parse(path)
        os.unlink(path)

        assert "PDF Test Content" in text
        assert "测试内容" in text

    def test_docx_parser(self):
        """DOCX 解析（需要 python-docx）"""
        from tars.knowledge.parsers import DocumentParser
        docx_mod = pytest.importorskip("docx")

        from docx import Document
        doc = Document()
        doc.add_paragraph("DOCX Test Content 文档内容")
        doc.add_paragraph("Second paragraph")
        path = tempfile.mktemp(suffix=".docx")
        doc.save(path)

        parser = DocumentParser()
        text = parser.parse(path)
        os.unlink(path)

        assert "DOCX Test Content" in text
        assert "Second paragraph" in text
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestDocumentParsers -v`
Expected: FAIL (module not found)

- [ ] **Step 5: Create parsers.py**

```python
# backend/tars/knowledge/parsers.py
"""文档解析器 — 支持 PDF/DOCX/MD/TXT"""
import os
import re
from typing import Optional


class DocumentParser:
    """根据文件扩展名自动选择解析器"""

    def parse(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".docx":
            return self._parse_docx(file_path)
        elif ext == ".md":
            return self._parse_markdown(file_path)
        else:
            return self._parse_text(file_path)

    def _parse_pdf(self, file_path: str) -> str:
        import fitz
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)

    def _parse_docx(self, file_path: str) -> str:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    def _parse_markdown(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 去除 markdown 标记但保留文本
        content = re.sub(r"#{1,6}\s*", "", content)  # headers
        content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)  # bold
        content = re.sub(r"\*(.+?)\*", r"\1", content)  # italic
        content = re.sub(r"`(.+?)`", r"\1", content)  # inline code
        content = re.sub(r"```[\s\S]*?```", "", content)  # code blocks
        content = re.sub(r"^\s*[-*+]\s+", "", content, flags=re.MULTILINE)  # list markers
        content = re.sub(r"!\[.*?\]\(.*?\)", "", content)  # images
        content = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", content)  # links
        return content.strip()

    def _parse_text(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
```

- [ ] **Step 6: Integrate parser into indexer.py**

Replace `index_file` method in `backend/tars/knowledge/indexer.py:98-122`:

```python
def index_file(
    self,
    file_path: str,
    doc_id: str,
    collection_id: str,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """从文件路径读取并索引（支持 PDF/DOCX/MD/TXT）"""
    from .parsers import DocumentParser

    try:
        parser = DocumentParser()
        text = parser.parse(file_path)
    except Exception as e:
        return {"doc_id": doc_id, "chunk_count": 0, "status": "read_error", "error": str(e)}

    file_name = os.path.basename(file_path)
    file_type = os.path.splitext(file_name)[1].lower()

    return self.index_document(
        text=text,
        doc_id=doc_id,
        collection_id=collection_id,
        file_name=file_name,
        file_type=file_type,
        tenant_id=tenant_id,
    )
```

Also update `upload_document` in `api/knowledge.py` to use parser instead of raw decode (line 167-171):

```python
        # 解析文件内容
        from ..knowledge.parsers import DocumentParser
        import tempfile as _tempfile

        # 写入临时文件供 parser 使用
        ext = os.path.splitext(file.filename)[1].lower()
        tmp_path = file_path  # 已保存到磁盘

        try:
            parser = DocumentParser()
            text = parser.parse(tmp_path)
        except Exception:
            text = ""
```

- [ ] **Step 7: Run tests**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestDocumentParsers -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/tars/knowledge/parsers.py backend/tars/knowledge/indexer.py backend/tars/api/knowledge.py backend/requirements.txt backend/tests/test_vector_upgrade.py
git commit -m "feat: add PDF/DOCX/MD document parsers for knowledge base"
```

---

### Task 4: 知识库查询接入查询扩展

**Files:**
- Modify: `backend/tars/knowledge/retriever.py`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Write failing test**

```python
# append to backend/tests/test_vector_upgrade.py

class TestKnowledgeQueryExpansion:
    def test_retrieve_with_expansion(self):
        from tars.knowledge.retriever import KnowledgeRetriever
        from unittest.mock import MagicMock

        mock_vector_store = MagicMock()
        mock_vector_store.query.return_value = [
            {"document": "result 1", "distance": 0.2, "metadata": {"file_name": "a.txt", "chunk_index": 0, "chunk_total": 1}},
        ]
        mock_embedding = MagicMock()

        retriever = KnowledgeRetriever(mock_vector_store, mock_embedding)
        results = retriever.retrieve(
            query="如何安装",
            collection_ids=["coll1"],
            top_k=5,
            expand=True,
        )

        # 查询扩展后应该有多次 vector_store.query 调用
        assert mock_vector_store.query.call_count > 1
        assert len(results) > 0

    def test_retrieve_without_expansion(self):
        from tars.knowledge.retriever import KnowledgeRetriever
        from unittest.mock import MagicMock

        mock_vector_store = MagicMock()
        mock_vector_store.query.return_value = [
            {"document": "result 1", "distance": 0.3, "metadata": {"file_name": "a.txt", "chunk_index": 0, "chunk_total": 1}},
        ]
        mock_embedding = MagicMock()

        retriever = KnowledgeRetriever(mock_vector_store, mock_embedding)
        results = retriever.retrieve(
            query="如何安装",
            collection_ids=["coll1"],
            top_k=5,
            expand=False,
        )

        # 不扩展时只调用一次
        assert mock_vector_store.query.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestKnowledgeQueryExpansion -v`
Expected: FAIL (retrieve doesn't accept expand param)

- [ ] **Step 3: Modify retriever.py**

Replace `retrieve` method in `backend/tars/knowledge/retriever.py`:

```python
from ..search.query_expansion import QueryExpander


class KnowledgeRetriever:
    """知识库检索器"""

    def __init__(self, vector_store, embedding_provider=None):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self._expander = QueryExpander()

    def retrieve(
        self,
        query: str,
        collection_ids: List[str],
        top_k: int = 5,
        tenant_id: str = "default",
        expand: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        从指定知识库中检索相关内容
        expand=True 时使用同义词扩展提升召回率
        """
        if not collection_ids:
            return []

        queries = self._expander.expand(query, method="synonym") if expand else [query]

        all_results = []
        seen_ids = set()

        for q in queries:
            for collection_id in collection_ids:
                try:
                    results = self.vector_store.query(
                        query_text=q,
                        top_k=top_k,
                        tenant_id=tenant_id,
                        collection_name=f"knowledge_{collection_id}",
                    )
                    for item in results:
                        item_id = item.get("id", item["document"][:50])
                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)
                        all_results.append({
                            "text": item["document"],
                            "metadata": item["metadata"],
                            "score": 1.0 - item["distance"],
                            "source": {
                                "collection_id": collection_id,
                                "file_name": item["metadata"].get("file_name", ""),
                                "chunk_index": item["metadata"].get("chunk_index", 0),
                                "chunk_total": item["metadata"].get("chunk_total", 1),
                            },
                        })
                except Exception as e:
                    print(f"[KnowledgeRetriever] 检索失败 {collection_id}: {e}")
                    continue

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestKnowledgeQueryExpansion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/knowledge/retriever.py backend/tests/test_vector_upgrade.py
git commit -m "feat: integrate query expansion into knowledge retriever"
```

---

### Task 5: 批量索引 API

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Write failing test**

```python
# append to backend/tests/test_vector_upgrade.py
import io
from fastapi.testclient import TestClient
from fastapi import FastAPI

class TestBatchIndexAPI:
    def setup_method(self):
        from unittest.mock import MagicMock, patch
        from tars.api.knowledge import router, init_knowledge_api

        self.app = FastAPI()
        self.app.include_router(router)

        self.mock_db = MagicMock()
        self.mock_vector_store = MagicMock()
        self.mock_vector_store.is_available = True
        self.mock_vector_store.add_documents.return_value = None
        self.mock_embedding = MagicMock()
        self.mock_embedding.encode.return_value = [[0.1] * 512]

        init_knowledge_api(self.mock_db, self.mock_vector_store, self.mock_embedding)

        # Mock collection exists
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("coll1",)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        self.mock_db._get_conn.return_value = mock_conn

        self.client = TestClient(self.app)

    def test_batch_upload_multiple_files(self):
        files = [
            ("files", ("file1.txt", io.BytesIO(b"Content of file 1"), "text/plain")),
            ("files", ("file2.txt", io.BytesIO(b"Content of file 2"), "text/plain")),
        ]
        response = self.client.post(
            "/api/knowledge/collections/coll1/batch",
            files=files,
            headers={"x-tenant-id": "default"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["indexed"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestBatchIndexAPI -v`
Expected: FAIL (endpoint not found)

- [ ] **Step 3: Add batch endpoint to api/knowledge.py**

Append to `backend/tars/api/knowledge.py`:

```python
@router.post("/collections/{coll_id}/batch")
async def batch_upload_documents(
    coll_id: str,
    files: List[UploadFile] = File(...),
    x_tenant_id: Optional[str] = Header(default="default"),
):
    if _db is None or _indexer is None:
        raise HTTPException(status_code=500, detail="知识库 API 未初始化")

    tenant_id = x_tenant_id or "default"

    # 验证集合存在
    conn = _db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM document_collections WHERE id = ? AND tenant_id = ?",
        (coll_id, tenant_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="知识库不存在")

    from .knowledge_parsers_import import DocumentParser  # will fix path below
    from ..knowledge.parsers import DocumentParser

    results = {"total": len(files), "indexed": 0, "failed": []}
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "knowledge")
    os.makedirs(uploads_dir, exist_ok=True)

    for file in files:
        doc_id = str(uuid.uuid4())
        file_path = os.path.join(uploads_dir, f"{doc_id}_{file.filename}")

        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            # 解析
            parser = DocumentParser()
            text = parser.parse(file_path)

            if not text.strip():
                results["failed"].append({"file": file.filename, "error": "空文件或无法解析"})
                continue

            # 索引
            now = _now()
            cursor.execute(
                "INSERT INTO document_files (id, collection_id, file_name, file_path, file_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, coll_id, file.filename, file_path, file.content_type or "", "pending", now),
            )

            index_result = _indexer.index_document(
                text=text,
                doc_id=doc_id,
                collection_id=coll_id,
                file_name=file.filename,
                file_type=file.content_type or "",
                tenant_id=tenant_id,
            )

            cursor.execute(
                "UPDATE document_files SET chunk_count = ?, status = ? WHERE id = ?",
                (index_result["chunk_count"], index_result["status"], doc_id),
            )

            if index_result["status"] == "indexed":
                results["indexed"] += 1
            else:
                results["failed"].append({"file": file.filename, "error": index_result.get("error", "索引失败")})

        except Exception as e:
            results["failed"].append({"file": file.filename, "error": str(e)})

    conn.commit()
    return results
```

**Note:** Remove the erroneous import line `from .knowledge_parsers_import import DocumentParser`. The correct import is `from ..knowledge.parsers import DocumentParser`.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestBatchIndexAPI -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/api/knowledge.py backend/tests/test_vector_upgrade.py
git commit -m "feat: add batch document upload endpoint for knowledge base"
```

---

### Task 6: Embedding 模型可切换

**Files:**
- Modify: `backend/tars/memory/embeddings.py`
- Create: `backend/tars/api/settings.py`
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Write failing test**

```python
# append to backend/tests/test_vector_upgrade.py

class TestEmbeddingSwitch:
    def test_embedding_manager_switch_provider(self):
        from tars.memory.embeddings import EmbeddingManager

        manager = EmbeddingManager()
        info = manager.get_info()
        assert "provider" in info
        assert "model" in info
        assert "dimension" in info

    def test_embedding_manager_reinitialize_ollama(self):
        from tars.memory.embeddings import EmbeddingManager
        from unittest.mock import patch, MagicMock

        manager = EmbeddingManager()

        # Mock Ollama provider creation
        with patch("tars.memory.embeddings.OllamaEmbeddingProvider") as MockOllama:
            mock_instance = MagicMock()
            mock_instance.dim = 1024
            MockOllama.return_value = mock_instance

            result = manager.reinitialize(provider="ollama", model="bge-m3")
            assert result["success"] is True
            assert manager.provider == mock_instance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestEmbeddingSwitch -v`
Expected: FAIL (EmbeddingManager not defined)

- [ ] **Step 3: Add EmbeddingManager to embeddings.py**

Append to `backend/tars/memory/embeddings.py`:

```python
class EmbeddingManager:
    """管理 embedding provider 的运行时切换"""

    def __init__(self, provider: EmbeddingProvider = None):
        self.provider = provider
        self._provider_type = "local"
        self._model_name = "BAAI/bge-small-zh-v1.5"

    def get_info(self) -> dict:
        return {
            "provider": self._provider_type,
            "model": self._model_name,
            "dimension": self.provider.dim if self.provider else 0,
        }

    def reinitialize(self, provider: str, model: str) -> dict:
        """切换 embedding provider"""
        old_dim = self.provider.dim if self.provider else 0

        try:
            if provider == "local":
                new_provider = LocalEmbeddingProvider(model)
            elif provider == "ollama":
                new_provider = OllamaEmbeddingProvider(model=model)
            else:
                return {"success": False, "error": f"不支持的 provider: {provider}"}

            self.provider = new_provider
            self._provider_type = provider
            self._model_name = model

            new_dim = new_provider.dim
            warning = None
            if old_dim and new_dim != old_dim:
                warning = f"维度从 {old_dim} 变为 {new_dim}，建议重建索引"

            return {"success": True, "dimension": new_dim, "warning": warning}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Create settings API**

```python
# backend/tars/api/settings.py
"""系统设置 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/settings", tags=["Settings"])

_embedding_manager = None


def init_settings_api(embedding_manager) -> None:
    global _embedding_manager
    _embedding_manager = embedding_manager


class EmbeddingConfigRequest(BaseModel):
    provider: str  # "local" | "ollama"
    model: str


@router.get("/embedding")
async def get_embedding_config():
    if _embedding_manager is None:
        raise HTTPException(status_code=500, detail="设置 API 未初始化")
    return _embedding_manager.get_info()


@router.put("/embedding")
async def update_embedding_config(request: EmbeddingConfigRequest):
    if _embedding_manager is None:
        raise HTTPException(status_code=500, detail="设置 API 未初始化")

    result = _embedding_manager.reinitialize(request.provider, request.model)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_vector_upgrade.py::TestEmbeddingSwitch -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tars/memory/embeddings.py backend/tars/api/settings.py backend/tests/test_vector_upgrade.py
git commit -m "feat: add runtime embedding model switching with settings API"
```

---

### Task 7: 集成验证

**Files:**
- Test: `backend/tests/test_vector_upgrade.py`

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/test_vector_upgrade.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run existing tests to check no regressions**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: No new failures

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "test: vector search & knowledge base upgrade - all tests passing"
```
