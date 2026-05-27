---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 向量搜索与知识库升级设计

## 升级项目

1. Reranker 集成到搜索管线
2. 文档删除修复
3. PDF/DOCX 文档解析
4. 知识库查询接入查询扩展
5. 批量索引 API
6. Embedding 模型可切换

## 一、Reranker 集成

### 当前流程
```
query → 语义搜索(top-20) + 关键词搜索 → 合并评分 → 返回 top-K
```

### 升级后
```
query → 语义搜索(top-20) + 关键词搜索 → 合并 → Reranker 精排 → 返回 top-K
```

### 实现
- `HybridSearch.search()` 最终返回前调用 `CrossEncoderReranker.rerank(query, candidates)`
- `SearchGateway` 同样在合并结果后调用 reranker
- 配置开关：`use_reranker: bool = True`
- 降级策略：模型加载失败时跳过 rerank，按原始分数排序
- 只对 top-20 候选精排，不影响性能

## 二、文档删除修复

### 当前问题
`KnowledgeIndexer.delete_document()` 返回 True 但未清理 Chroma 中的 chunks。

### 修复逻辑
```python
def delete_document(self, doc_id: str, collection_id: str) -> bool:
    # 1. 获取文档信息
    doc = self.db.get_document(doc_id)
    if not doc:
        return False
    # 2. 构造 chunk IDs 并从 Chroma 删除
    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(doc.chunk_count)]
    collection = self.vector_store.get_collection(f"knowledge_{collection_id}")
    collection.delete(ids=chunk_ids)
    # 3. 删除数据库记录
    self.db.delete_document_file(doc_id)
    return True
```

## 三、PDF/DOCX 文档解析

### 新增文件：`knowledge/parsers.py`

```python
class DocumentParser:
    def parse(self, file_path: str) -> str:
        """根据扩展名自动选择解析器，返回纯文本"""

class PDFParser:
    # pymupdf (fitz)，逐页提取文本

class DOCXParser:
    # python-docx，逐段落提取

class MarkdownParser:
    # 去除标记符号，保留结构

class TextParser:
    # UTF-8 读取（现有逻辑）
```

### 支持格式
| 扩展名 | 解析器 | 依赖 |
|--------|--------|------|
| .pdf | PDFParser | pymupdf |
| .docx | DOCXParser | python-docx |
| .md | MarkdownParser | 内置 |
| .txt | TextParser | 内置 |

### 集成点
`KnowledgeIndexer.index_document()` 中替换现有的 UTF-8 读取为 `DocumentParser.parse()`。

## 四、知识库查询接入查询扩展

### 当前
```python
KnowledgeRetriever.retrieve(query) → 单次向量检索
```

### 升级后
```python
KnowledgeRetriever.retrieve(query, expand=True):
    if expand:
        variants = QueryExpansion.expand(query)  # 原始 + 3 个变体
    else:
        variants = [query]
    results = []
    for q in variants:
        results += vector_search(q, top_k=10)
    return deduplicate_and_rank(results, top_k=top_k)
```

- `expand` 参数默认 True
- 多变体结果按最高分去重
- 不增加额外 API 调用（synonym 扩展不需要 LLM）

## 五、批量索引 API

### 新增端点
```
POST /api/knowledge/collections/{id}/batch
Content-Type: multipart/form-data
Body: files[] (多文件)

Response:
{
  "total": 5,
  "indexed": 4,
  "failed": [{"file": "corrupt.pdf", "error": "无法解析"}]
}
```

### 实现
- 逐文件：解析 → 分块 → 生成 embedding → 写入 Chroma
- 单文件失败不影响其他文件
- 返回汇总结果

## 六、Embedding 模型可切换

### API
```
GET  /api/settings/embedding
Response: { "provider": "local", "model": "BAAI/bge-small-zh-v1.5", "dimension": 512 }

PUT  /api/settings/embedding
Body: { "provider": "local|ollama", "model": "bge-small-zh-v1.5" }
Response: { "success": true, "warning": "维度变化，建议重建索引" }
```

### 实现
- `EmbeddingProvider` 增加 `reinitialize(provider, model)` 方法
- 切换后更新全局 embedding_provider 实例
- 维度变化时返回 warning（不自动重建）
- 新增 `POST /api/settings/embedding/rebuild-index` 手动触发全量重建

### 支持模型
- local: `BAAI/bge-small-zh-v1.5` (512d), `BAAI/bge-base-zh-v1.5` (768d)
- ollama: 从 Ollama API 拉取可用 embedding 模型列表

## 七、文件变更

| 文件 | 操作 |
|------|------|
| `memory/search.py` | 插入 reranker 调用 |
| `search/gateway.py` | 插入 reranker 调用 |
| `knowledge/indexer.py` | 修复 delete_document，集成 DocumentParser |
| `knowledge/parsers.py` | **新增** 文档解析器 |
| `knowledge/retriever.py` | 接入 QueryExpansion |
| `api/knowledge.py` | 新增 batch 端点 |
| `api/settings.py` | 新增 embedding 配置端点 |
| `memory/embeddings.py` | 支持运行时切换 + reinitialize |
| `requirements.txt` | 新增 pymupdf, python-docx |

## 八、新增依赖

```
pymupdf>=1.24.0
python-docx>=1.1.0
```

## 九、实施顺序

```
Step 1: 文档删除修复（最小改动，修 bug）
Step 2: Reranker 集成（接入已有代码）
Step 3: PDF/DOCX 解析器（新增文件，不影响现有）
Step 4: 知识库查询扩展（改 retriever）
Step 5: 批量索引 API（新增端点）
Step 6: Embedding 模型切换（涉及全局状态）
```
