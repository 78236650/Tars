# TARS 向量搜索与知识库升级计划

## 背景

TARS 当前搜索系统存在以下核心瓶颈：
1. **语义搜索性能差**: embedding 存储在 SQLite BLOB 中，搜索时全表加载到内存计算余弦相似度，O(N) 复杂度
2. **无文档知识库**: 上传的 PDF/Word/Excel 仅解析为文本，不建立索引，无法做"基于我的文档回答"
3. **无结果重排序**: 初始召回后没有精排阶段，Top-K 质量受限
4. **FTS5 中文弱**: 无中文分词器，CJK 文本依赖 LIKE fallback
5. **无搜索缓存**: 相同查询重复计算 embedding 和 FTS5

## 目标

- 引入 Chroma 向量数据库，替换 SQLite BLOB 存储
- 构建文档知识库系统（上传 → 分块 → embedding → 索引 → RAG 检索）
- 引入 Cross-Encoder 重排序，提高搜索结果精准度
- 添加查询扩展和搜索缓存机制
- 保持与现有记忆系统的兼容性

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                        统一搜索入口 (SearchGateway)                    │
├─────────────────────────────────────────────────────────────────────┤
│  查询分析 → QueryExpansion → 多路召回 → 融合打分 → CrossEncoder重排   │
├────────────┬─────────────┬──────────────┬─────────────┬────────────┤
│  网络搜索路 │  记忆向量路  │  文档知识库   │  FTS关键词路 │  实体关系路 │
│ WebSearch  │  Chroma     │  Chroma      │ SQLite FTS5 │  SQLite    │
│            │ (memories)  │ (documents)  │             │            │
└────────────┴─────────────┴──────────────┴─────────────┴────────────┘
```

## 实施步骤

### Step 1: 引入 Chroma 向量数据库

**1.1 添加依赖**
- `backend/requirements.txt` 添加 `chromadb>=0.5.0`

**1.2 创建 Chroma 客户端封装**
- 新建 `backend/tars/vectorstore/__init__.py`
- 新建 `backend/tars/vectorstore/chroma_client.py`
  - `ChromaVectorStore` 类：封装 collection 管理、增删改查
  - 支持多租户（按 tenant_id 分 collection）
  - 提供 `add_documents()`, `query()`, `delete()`, `update()` 接口
  - 持久化路径：`backend/data/vectorstore/`

**1.3 记忆系统迁移到 Chroma**
- 修改 `backend/tars/memory/search.py`:
  - `HybridSearch._semantic_score()` 从 SQLite BLOB 全表扫描改为 Chroma 向量查询
  - 保留 FTS 关键词搜索作为补充
  - 保留 Ebbinghaus 衰减评分逻辑
- 修改 `backend/tars/memory/archival.py`:
  - `ArchivalManager.insert()` 写入记忆时同步写入 Chroma
  - 生成 embedding 后同时存 SQLite BLOB（兼容）和 Chroma（新）
- 修改 `backend/tars/memory/manager.py`:
  - `MemoryManager.__init__()` 初始化时传入 Chroma client
  - 提供数据迁移方法：将现有 SQLite embedding 批量导入 Chroma

**1.4 验证**
- 测试 Chroma 向量查询性能（1000/10000/100000 条记忆）
- 验证与现有记忆系统的兼容性

### Step 2: 构建文档知识库系统

**2.1 数据库模型**
- `backend/tars/database/base.py` 新增 `document_collections` 表：
  - id, tenant_id, name, description, created_at, updated_at
- 新增 `document_files` 表：
  - id, collection_id, file_name, file_path, file_type, chunk_count, status, created_at

**2.2 文档分块与索引**
- 新建 `backend/tars/knowledge/__init__.py`
- 新建 `backend/tars/knowledge/chunker.py`:
  - `DocumentChunker` 类：支持多种分块策略
  - 固定长度分块（默认 500 tokens，重叠 50）
  - 按段落分块（基于换行符）
  - 递归分块（先按段落，再按句子）
  - 元数据保留：文件名、页码、chunk 序号
- 新建 `backend/tars/knowledge/indexer.py`:
  - `KnowledgeIndexer` 类：文档 → 分块 → embedding → Chroma 索引
  - 支持 PDF/Word/Excel/TXT/Markdown
  - 进度追踪（chunk_count, indexed_count）

**2.3 知识库检索**
- 新建 `backend/tars/knowledge/retriever.py`:
  - `KnowledgeRetriever` 类：向量检索 + 关键词过滤 + 重排序
  - `retrieve(query, collection_ids, top_k=5)` 接口
  - 返回带元数据的结果（来源文件、页码、相似度）

**2.4 API 路由**
- 新建 `backend/tars/api/knowledge.py`:
  - `POST /api/knowledge/collections` — 创建知识库
  - `GET /api/knowledge/collections` — 列出知识库
  - `DELETE /api/knowledge/collections/{id}` — 删除知识库
  - `POST /api/knowledge/collections/{id}/documents` — 上传文档
  - `GET /api/knowledge/collections/{id}/documents` — 列出文档
  - `DELETE /api/knowledge/collections/{id}/documents/{doc_id}` — 删除文档
  - `POST /api/knowledge/search` — 跨库搜索
  - `POST /api/knowledge/collections/{id}/query` — 单库查询

**2.5 工具注册**
- 新建 `backend/tars/tools/builtin/knowledge_search.py`:
  - `KnowledgeSearchTool`: 供 Agent 调用，自然语言查询知识库
  - 参数：query, collection_id（可选）, top_k

**2.6 前端组件**
- 新建 `frontend/src/components/knowledge/KnowledgeManager.vue`:
  - 知识库 CRUD
  - 文档上传/删除
  - 搜索测试
- 新建 `frontend/src/components/knowledge/DocumentUploader.vue`
- 扩展 `frontend/src/api/index.ts` 添加 `knowledgeApi`
- 扩展 `frontend/src/types/index.ts` 添加知识库类型

### Step 3: Cross-Encoder 重排序

**3.1 重排序器实现**
- 新建 `backend/tars/reranker/__init__.py`
- 新建 `backend/tars/reranker/cross_encoder.py`:
  - `CrossEncoderReranker` 类：基于 sentence-transformers 的 Cross-Encoder
  - 默认模型：`cross-encoder/ms-marco-MiniLM-L-6-v2`（轻量，效果好）
  - `rerank(query, documents, top_k=5)` 接口
  - 输入：查询 + 候选文档列表
  - 输出：按相关性排序的文档列表

**3.2 集成到搜索流程**
- 修改 `backend/tars/memory/search.py`:
  - `HybridSearch.search()` 召回阶段扩大到 limit * 3
  - 增加重排序阶段：Cross-Encoder 对召回结果精排
  - 最终返回 top limit
- 修改 `backend/tars/knowledge/retriever.py`:
  - `KnowledgeRetriever.retrieve()` 同样集成重排序

**3.3 配置化**
- `backend/tars/config/memory.py` 新增：
  - `reranker_enabled`: bool
  - `reranker_model`: str
  - `reranker_top_k`: int（召回数量）

### Step 4: 查询扩展与搜索缓存

**4.1 查询扩展 (Query Expansion)**
- 新建 `backend/tars/search/query_expansion.py`:
  - `QueryExpander` 类：基于 LLM 生成同义词/相关词
  - `expand(query, method="llm")` 接口
  - 方法：llm（调用 LLM）/ synonym（同义词词典）/ hybrid（两者结合）
  - 扩展后的查询用于 FTS5 和向量搜索

**4.2 搜索缓存**
- 新建 `backend/tars/search/cache.py`:
  - `SearchCache` 类：基于 SQLite 的查询结果缓存
  - 表结构：query_hash, query_text, results_json, created_at, ttl
  - 缓存 key：查询文本 + 搜索类型 + limit 的 hash
  - TTL：默认 1 小时（网络搜索）/ 5 分钟（记忆搜索）/ 10 分钟（知识库搜索）

**4.3 统一搜索网关**
- 新建 `backend/tars/search/gateway.py`:
  - `SearchGateway` 类：统一入口，协调各路搜索
  - `search(query, sources=["memory", "knowledge", "web"], limit=5)` 接口
  - 自动选择搜索源、查询扩展、缓存检查、多路召回、重排序

### Step 5: 前端集成

**5.1 知识库管理页面**
- 新建 `frontend/src/views/KnowledgeView.vue`:
  - 路由：`/knowledge`
  - 知识库列表 + 创建/删除
  - 文档上传（拖拽 + 进度）
  - 搜索测试面板

**5.2 聊天集成**
- 扩展 `frontend/src/components/chat/ChatPanel.vue`:
  - 显示知识库引用来源（文件名、页码）
  - 引用卡片可点击跳转

**5.3 侧边栏导航**
- `frontend/src/components/layout/Sidebar.vue`:
  - 新增 "知识库" 导航项

### Step 6: 测试与验证

**6.1 单元测试**
- 测试 Chroma 向量查询正确性
- 测试文档分块边界情况
- 测试 Cross-Encoder 重排序效果
- 测试查询扩展质量

**6.2 集成测试**
- 端到端：上传 PDF → 索引 → 查询 → 返回正确结果
- 性能测试：1000 条记忆查询耗时 < 100ms
- 并发测试：多租户同时查询

**6.3 回归测试**
- 验证现有记忆系统不受影响
- 验证 Agent 对话流程正常

## 文件清单

### 新增文件
| 文件 | 说明 |
|------|------|
| `backend/tars/vectorstore/__init__.py` | 向量数据库包 |
| `backend/tars/vectorstore/chroma_client.py` | Chroma 客户端封装 |
| `backend/tars/knowledge/__init__.py` | 知识库包 |
| `backend/tars/knowledge/chunker.py` | 文档分块 |
| `backend/tars/knowledge/indexer.py` | 文档索引 |
| `backend/tars/knowledge/retriever.py` | 知识库检索 |
| `backend/tars/reranker/__init__.py` | 重排序包 |
| `backend/tars/reranker/cross_encoder.py` | Cross-Encoder 实现 |
| `backend/tars/search/__init__.py` | 搜索包 |
| `backend/tars/search/query_expansion.py` | 查询扩展 |
| `backend/tars/search/cache.py` | 搜索缓存 |
| `backend/tars/search/gateway.py` | 统一搜索网关 |
| `backend/tars/api/knowledge.py` | 知识库 API |
| `backend/tars/tools/builtin/knowledge_search.py` | 知识库搜索工具 |
| `frontend/src/components/knowledge/KnowledgeManager.vue` | 知识库管理组件 |
| `frontend/src/components/knowledge/DocumentUploader.vue` | 文档上传组件 |
| `frontend/src/views/KnowledgeView.vue` | 知识库页面 |

### 修改文件
| 文件 | 修改内容 |
|------|----------|
| `backend/requirements.txt` | 添加 chromadb, sentence-transformers |
| `backend/tars/database/base.py` | 新增 document_collections, document_files 表 |
| `backend/tars/memory/search.py` | 接入 Chroma 向量查询 |
| `backend/tars/memory/archival.py` | 写入时同步 Chroma |
| `backend/tars/memory/manager.py` | 传入 Chroma client |
| `backend/tars/memory/router.py` | 接入 SearchGateway |
| `backend/tars/config/memory.py` | 新增 reranker 配置 |
| `backend/tars/main.py` | 初始化 Chroma、知识库、搜索网关 |
| `frontend/src/api/index.ts` | 添加 knowledgeApi |
| `frontend/src/types/index.ts` | 添加知识库类型 |
| `frontend/src/router/index.ts` | 添加 /knowledge 路由 |
| `frontend/src/i18n/index.ts` | 添加 nav.knowledge 翻译 |
| `frontend/src/components/layout/Sidebar.vue` | 新增知识库导航 |
| `frontend/src/components/chat/ChatPanel.vue` | 显示知识库引用 |

## 依赖

```
chromadb>=0.5.0
sentence-transformers>=3.0.0
```

## 风险与回滚

| 风险 | 缓解措施 |
|------|----------|
| Chroma 初始化失败 | 降级到现有 SQLite BLOB 搜索 |
| embedding 模型加载失败 | 纯 FTS5 关键词搜索降级 |
| 数据迁移失败 | 保留 SQLite BLOB，双写一段时间后切换 |
| 性能不达预期 | 调整 HNSW 参数（nlist, ef） |

## 验收标准

- [ ] Chroma 向量查询 10000 条记忆 < 50ms
- [ ] 上传 PDF 后能准确回答文档内容相关问题
- [ ] Cross-Encoder 重排序后 Top-5 准确率提升 > 20%
- [ ] 查询缓存命中率 > 30%（重复查询场景）
- [ ] 现有记忆系统功能不受影响（回归测试通过）
- [ ] 前端构建通过，无 TypeScript 错误
