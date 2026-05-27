---
doc_type: plan
status: shipped
platform_version: 4.3.1
catalog: docs/superpowers/README.md
---
# 知识库深度入库与文档浏览 — 实施计划（v4.3.1）

> **For agentic workers:** 推荐使用 superpowers:subagent-driven-development 按 Task 逐步执行。步骤使用 `- [ ]` 跟踪进度。

**Goal:** 让知识库从「原文碎片索引」升级为「入库深度理解 + 文档浏览摘要准确」，优先交付 DocumentDetailDrawer 与 DocProfile。

**Architecture:** Parse → Enrich（LLM）→ MultiType Chunk → Index；浏览层直读 `document_profiles`，检索层多路召回 summary/passage。

**Tech Stack:** Python 3.11 / FastAPI / SQLite / Chroma / Vue 3 / pytest / vitest

**Spec:** [2026-05-24-knowledge-deep-ingest-design.md](../specs/2026-05-24-knowledge-deep-ingest-design.md)

---

## 里程碑

| 里程碑 | 交付物 | 验收 |
|--------|--------|------|
| **M1 — 数据与 Enricher** | document_profiles 表 + KnowledgeEnricher + 入库写 profile | 单测通过；上传 txt 后可查 profile JSON |
| **M2 — 浏览 UI** | DocumentDetailDrawer + profile API + 列表 one_liner | 前端可浏览摘要/要点/目录 |
| **M3 — 结构解析** | DOCX/PPTX/XLSX 结构 + 分类型 chunk 参数 | 4 类样例文档章节正确 |
| **M4 — 搜索与迁移** | browse 搜索 + reindex + ref API 升级 | 集合搜索优先 summary；旧文档可 re-enrich |

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/tars/database/base.py` | Modify | `document_profiles` 表；`document_files` 新字段；`document_collections.default_doc_type` |
| `backend/tars/knowledge/models.py` | Create | ParsedDocument, DocProfile, SectionSummary, MetricsTable dataclasses |
| `backend/tars/knowledge/enricher.py` | Create | LLM enrichment + Map-Reduce + 启发式 confidence；按租户 `resolve_insight_llm` 取 provider |
| `backend/tars/knowledge/enricher_prompts.py` | Create | policy/proposal/generic prompts（metrics 不走通用 prompt） |
| `backend/tars/knowledge/metrics_extractor.py` | Create | XLSX/CSV 结构化抽取 → MetricsTable → key_fact chunks |
| `backend/tars/knowledge/profile_store.py` | Create | profile CRUD |
| `backend/tars/knowledge/structure_parser.py` | Create | **入口路由**：扩展名/集合默认类型→解析器，`infer_doc_type`，返回 ParsedDocument |
| `backend/tars/knowledge/parsers.py` | Modify | 各扩展名底层解析器返回 ParsedDocument；新增 PPTX；MD 保留标题；DOCX/PDF 升级 |
| `backend/tars/knowledge/chunker.py` | Modify | chunk_type、section 边界、parent_section_id |
| `backend/tars/knowledge/indexer.py` | Modify | 接收 `(parsed, profile)`，写衍生 chunk + profile；**stateless 不持有 provider** |
| `backend/tars/knowledge/access.py` | Modify | browse 搜索模式；按 chunk_type 判断 source_type |
| `backend/tars/api/knowledge.py` | Modify | 异步入库 + profile/passages/re-enrich/reindex API + ref API 升级 |
| `backend/config/knowledge.yaml` | Create | enrichment + chunking + reindex 配置 |
| `backend/tars/main.py` | Modify | 加载 knowledge.yaml；init_knowledge_api 注入 llm_settings_store |
| `backend/tests/test_knowledge_enricher.py` | Create | Enricher 单测 |
| `backend/tests/test_knowledge_profile_api.py` | Create | API 单测 |
| `backend/tests/test_knowledge_structure_parser.py` | Create | 解析器单测 |
| `backend/tests/test_knowledge_metrics_extractor.py` | Create | metrics 专路单测 |
| `backend/tests/fixtures/knowledge/` | Create | 4 类样例文档（小体积） |
| `frontend/src/components/knowledge/DocumentDetailDrawer.vue` | Create | 文档详情浏览（含状态轮询） |
| `frontend/src/components/knowledge/KnowledgeManager.vue` | Modify | 列表摘要 + 打开详情 + 搜索分组 |
| `frontend/src/api/index.ts` | Modify | knowledgeApi.getProfile 等 |
| `frontend/src/types/index.ts` | Modify | DocProfile 类型 |
| `frontend/src/i18n/index.ts` | Modify | 新文案键 |
| `frontend/src/components/knowledge/KnowledgeManager.spec.ts` | Modify | 详情抽屉测试 |
| `scripts/acceptance/knowledge-deep-ingest.sh` | Create | 人工验收脚本 |

---

## Phase 1 — 数据模型与 Enricher（M1）

### Task 0: LLM Provider 注入与异步骨架（前置，必须先做）

> **背景：** 当前 [api/knowledge.py:26-37](../../../backend/tars/api/knowledge.py#L26-L37) `init_knowledge_api` 是进程级 singleton，**不带 LLM Provider**。Enricher 需要按租户解析 provider，且入库流程必须异步化，否则中等 PDF 会让前端卡 1–2 分钟。

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Modify: `backend/tars/main.py`

- [ ] **Step 1:** `init_knowledge_api()` 新增参数 `llm_settings_store: InsightLlmSettingsStore`；`main.py` 启动时注入（复用 Insight 的 store）
- [ ] **Step 2:** 在 `backend/tars/knowledge/` 模块内**不持有** provider 实例；Enricher 在每次 `enrich()` 调用时 `resolve_insight_llm(store.get(tenant_id))`，与 [insight/job_runner.py:95-117](../../../backend/tars/insight/job_runner.py#L95-L117) 保持一致
- [ ] **Step 3:** 引入入库后台调度（参考 [api/meeting.py:266-270](../../../backend/tars/api/meeting.py#L266-L270)）：上传 endpoint 立即返回 `{id, status: "pending"}`，`asyncio.create_task` 跑 `_run_ingest(doc_id, ...)`
- [ ] **Step 4:** `_run_ingest` 内按状态机推进：`pending → parsing → enriching → indexing → ready`（或失败分支），每一步 `db.update_document_file(status=...)`
- [ ] **Step 5:** 单测：mock LLM store，assert 上传后异步任务能跑到 `ready` 状态

### Task 1: 数据库 schema

**Files:**
- Modify: `backend/tars/database/base.py`
- Test: `backend/tests/test_knowledge_profile_api.py`（schema 部分）

- [ ] **Step 1:** 添加 `document_profiles` 表及索引
- [ ] **Step 2:** `document_files` 增加 `doc_type`, `profile_ready`, `one_liner`；扩展 `status` 枚举值
- [ ] **Step 3:** `document_collections` 增加 `default_doc_type` 列
- [ ] **Step 4:** 编写迁移逻辑（`ALTER TABLE` try/except 兼容旧库）
- [ ] **Step 5:** 测试：新库建表 + 旧库迁移不报错

### Task 2: 领域模型

**Files:**
- Create: `backend/tars/knowledge/models.py`

- [ ] **Step 1:** 定义 `DocumentSection`, `ParsedDocument`, `SectionSummary`, `GlossaryItem`, `QAPair`, `DocProfile`, `MetricsTable`
- [ ] **Step 2:** 添加 `to_dict()` / `from_dict()` 序列化
- [ ] **Step 3:** 单测：round-trip 序列化

### Task 3: KnowledgeEnricher（含 metrics 专路）

**Files:**
- Create: `backend/tars/knowledge/enricher.py`
- Create: `backend/tars/knowledge/enricher_prompts.py`
- Create: `backend/tars/knowledge/metrics_extractor.py`
- Create: `backend/tests/test_knowledge_enricher.py`
- Create: `backend/tests/test_knowledge_metrics_extractor.py`

- [ ] **Step 1:** 编写 failing test — mock LLM 返回 JSON，assert DocProfile 字段完整
- [ ] **Step 2:** 实现 `enrich(parsed, tenant_id, doc_type, llm_override=None)` 短文档路径；通过 `resolve_insight_llm(store.get(tenant_id))` 取 provider
- [ ] **Step 3:** 实现 Map-Reduce 长文档路径，阈值按 `min(provider.context_window * 0.6, max_input_chars)` 自适应
- [ ] **Step 4:** 实现降级：`enabled=false` / 无 provider / Map 段数>30 → `parse_warnings` 标注 + 退化采样或返回 `None`
- [ ] **Step 5:** 实现启发式 confidence 合成（parse_warnings、truncation_ratio、section_coverage、json_repair_used）
- [ ] **Step 6:** **metrics 专路**：`metrics_extractor.extract(parsed)` → `MetricsTable[]` → 每条指标转 `key_fact` chunk；**不调用通用 enrich prompt**，仅可选用 LLM 整理 glossary
- [ ] **Step 7:** 3 种 doc_type（policy/proposal/generic）prompt 模板单测；metrics 路径独立验证表头映射

### Task 4: profile_store

**Files:**
- Create: `backend/tars/knowledge/profile_store.py`

- [ ] **Step 1:** `save_profile(db, profile, tenant_id, collection_id)`
- [ ] **Step 2:** `get_profile(db, doc_id)` / `delete_profile(db, doc_id)`
- [ ] **Step 3:** `list_profiles_by_collection(db, collection_id)`
- [ ] **Step 4:** 单测 CRUD

### Task 5: Indexer 重构 + 异步入库串联

**Files:**
- Modify: `backend/tars/knowledge/indexer.py`
- Modify: `backend/tars/api/knowledge.py`
- Modify: `backend/tests/test_vector_search_knowledge_base.py`

- [ ] **Step 1:** `indexer.index_document(parsed: ParsedDocument, profile: DocProfile|None, ...)` 改造；indexer **不再持有** provider，保持 stateless
- [ ] **Step 2:** 写入衍生 chunks（doc_summary, section_summary, key_fact, synthetic_qa, glossary）带 `chunk_type` + `parent_section_id` metadata
- [ ] **Step 3:** Task 0 的 `_run_ingest` 串联：`structure_parser → enricher → indexer → profile_store`，每段失败后状态机走对应分支
- [ ] **Step 4:** 上传 API 同步返回 `{id, status: "pending"}`；新增 `GET .../status` 轻量轮询接口（仅返回 status + profile_ready）
- [ ] **Step 5:** 更新 `delete_document` 同时删 profile + 所有 chunk_type
- [ ] **Step 6:** 集成测试：mock enricher，assert 异步流程跑完后 chunk_count 含衍生块、profile_ready=true

**M1 验收：** 上传 `.txt` 测试文档 → 轮询 status 到 `ready` → `GET profile` 返回 summary + key_points

---

## Phase 2 — 浏览 API 与前端（M2）

### Task 6: Profile API

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Create: `backend/tests/test_knowledge_profile_api.py`

- [ ] **Step 1:** `GET /collections/{coll_id}/documents/{doc_id}/profile`
- [ ] **Step 2:** `GET .../passages?section_id=` — 返回 section 下 passage chunks
- [ ] **Step 3:** `GET .../status` — 轻量轮询，仅返回 `{status, profile_ready, progress?}`
- [ ] **Step 4:** `POST .../re-enrich` — 重跑 enricher（异步，立即返回 pending）
- [ ] **Step 5:** 升级 `GET /ref/{doc_id}` — **同时返回** `one_liner / summary_excerpt / chunk_excerpt`，保留旧 `snippet` 为 `chunk_excerpt` 别名
- [ ] **Step 6:** API 测试全覆盖

### Task 7: 前端类型与 API

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1:** 添加 `DocProfile`, `DocumentSectionSummary` 类型
- [ ] **Step 2:** `knowledgeApi.getDocumentProfile(collId, docId)`
- [ ] **Step 3:** `knowledgeApi.getDocumentPassages(...)`, `reEnrichDocument(...)`

### Task 8: DocumentDetailDrawer

**Files:**
- Create: `frontend/src/components/knowledge/DocumentDetailDrawer.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1:** Drawer 布局：标题区 / 一句话 / 摘要 / 要点 / 关键事实 / 目录 / 术语 / 元信息
- [ ] **Step 2:** 章节「展开原文」调用 passages API
- [ ] **Step 3:** 状态处理：`pending/parsing/enriching` 时**轮询** `GET status`（2s 间隔，60s 超时），`enrichment_failed` 显示「重新理解」按钮
- [ ] **Step 4:** 低置信度（`confidence < 阈值`）显示「建议核对原文」徽章
- [ ] **Step 5:** KnowledgeManager 文档行显示 one_liner + doc_type 标签 + 状态徽章 + 点击打开 Drawer
- [ ] **Step 6:** i18n 中英文键

### Task 9: 前端测试

**Files:**
- Modify: `frontend/src/components/knowledge/KnowledgeManager.spec.ts`

- [ ] **Step 1:** mock profile API，assert Drawer 渲染 summary 与 key_points
- [ ] **Step 2:** assert 无 profile 时显示「一键理解」

**M2 验收：** 浏览器打开知识库 → 点击文档 → 3 秒内看到结构化摘要

---

## Phase 3 — 结构感知解析（M3）

### Task 10: structure_parser

**Files:**
- Create: `backend/tars/knowledge/structure_parser.py`
- Create: `backend/tests/test_knowledge_structure_parser.py`
- Create: `backend/tests/fixtures/knowledge/`

- [ ] **Step 1:** 准备 4 个 fixture：policy.docx, proposal.pptx, metrics.xlsx, generic.md
- [ ] **Step 2:** `infer_doc_type()` 单测
- [ ] **Step 3:** DOCX heading 解析 → sections 层级正确
- [ ] **Step 4:** PPTXParser — 每 slide 一个 section
- [ ] **Step 5:** XLSXParser — 每 sheet 一个 section，表头识别
- [ ] **Step 6:** MarkdownParser 修复 — 保留 `#` 标题

### Task 11: 分类型分块

**Files:**
- Modify: `backend/tars/knowledge/chunker.py`
- Create: `backend/config/knowledge.yaml`

- [ ] **Step 1:** `chunk_by_sections(sections, profile_config)` — section 边界不切断
- [ ] **Step 2:** 从 yaml 读取 doc_type → chunk_size/overlap
- [ ] **Step 3:** passage chunk 写入 section_id / section_title metadata
- [ ] **Step 4:** 单测：policy fixture 条款不被 mid-sentence 切断

### Task 12: 上传 doc_type override

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Modify: `frontend/src/components/knowledge/DocumentUploader.vue`（可选下拉）

- [ ] **Step 1:** 上传 Form 支持 `doc_type` 可选参数
- [ ] **Step 2:** collection 级别默认 doc_type（metadata 或 description 约定，可选）

**M3 验收：** 4 类 fixture 入库后 profile.sections 数量与人工预期一致

---

## Phase 4 — 搜索升级与迁移（M4）

### Task 13: Browse 搜索模式

**Files:**
- Modify: `backend/tars/knowledge/access.py`
- Modify: `backend/tars/knowledge/retriever.py`
- Modify: `backend/tars/api/knowledge.py`

- [ ] **Step 1:** `search_knowledge(..., mode="browse")` — 过滤/加权 chunk_type in (doc_summary, section_summary, key_fact)
- [ ] **Step 2:** 结果按 doc_id 合并，避免同 doc 占满 top_k
- [ ] **Step 3:** 集合 query API 支持 `mode` 参数
- [ ] **Step 4:** KnowledgeManager 搜索抽屉 — 文档级结果 + 片段级结果分组展示

### Task 14: 存量 reindex（含成本预估与确认）

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Create: `scripts/acceptance/knowledge-deep-ingest.sh`

- [ ] **Step 1:** `POST /collections/{coll_id}/reindex/estimate` — 返回 `{doc_count, est_tokens, est_cost?}`，参数：`doc_ids?`
- [ ] **Step 2:** `POST /collections/{coll_id}/reindex` — 接受 `confirm=true`；当文档数 ≥ `reindex.require_confirm_above_doc_count` 且未确认时返回 412 + estimate
- [ ] **Step 3:** 前端在调用 reindex 前先调 estimate，弹确认框展示 token 估算
- [ ] **Step 4:** 无 profile 文档：详情页「一键理解」= 单 doc reindex（不走 estimate 闸门）
- [ ] **Step 5:** 验收脚本：上传 → 轮询 status → profile → search → ref API

### Task 15: Agent 引用增强（P2，可并行）

**Files:**
- Modify: `backend/tars/knowledge/access.py`
- Modify: `backend/tars/agent/agent.py`

- [ ] **Step 1:** `format_citation_results` — 每条附带 doc one_liner
- [ ] **Step 2:** Agent `_build_knowledge_context` 启用 `retrieve_with_context`

**M4 验收：** 集合内搜索「制度」→ 第一条为 doc_summary；旧文档 re-enrich 后 profile_ready=true

---

## 配置与依赖

### 新增 Python 依赖

```
python-pptx   # PPTX 解析
```

（`pymupdf`, `python-docx`, `openpyxl` 已有）

### knowledge.yaml 初始值

```yaml
knowledge:
  enrichment:
    enabled: true
    timeout_sec: 120
    max_input_chars: 48000
    confidence_threshold: 0.6
    json_repair_retries: 1
    budget_per_doc_tokens: 30000
    synthetic_qa_max: 3
    glossary_max: 20
    key_facts_max: 30
  chunking:
    profiles:
      policy:   { chunk_size: 1000, overlap: 150 }
      proposal: { chunk_size: 800,  overlap: 120 }
      metrics:  { chunk_size: 600,  overlap: 80 }
      generic:  { chunk_size: 900,  overlap: 120 }
  reindex:
    require_confirm_above_doc_count: 5
    estimate_tokens_per_doc: 8000
```

---

## 测试计划

### 单元测试

```bash
cd backend && .venv/bin/python -m pytest tests/test_knowledge_enricher.py tests/test_knowledge_profile_api.py tests/test_knowledge_structure_parser.py -q
```

### 前端测试

```bash
cd frontend && npm run test -- KnowledgeManager.spec.ts
```

### 人工验收（scripts/acceptance/knowledge-deep-ingest.sh）

1. 启动 backend + frontend
2. 创建集合「制度测试」
3. 上传 4 类 fixture
4. 逐个打开 DocumentDetailDrawer，检查摘要/要点/目录
5. 集合内搜索关键词，确认 browse 模式命中 summary
6. 调用 re-enrich，确认 profile 更新

---

## 风险缓冲

| 项 | 缓冲 |
|----|------|
| LLM JSON 解析失败 | enricher 内置 repair prompt + 配置化 retry（默认 1 次） |
| LLM 摘要幻觉 | 启发式 confidence + UI「建议核对原文」徽章 + 要点旁链 passage |
| metrics 表幻觉 | XLSX 走结构化抽取专路，**不让 LLM 抄表** |
| PPT 解析复杂 | Phase 3 可先交付 pptx 文字页；图片页 warning |
| 前端 Drawer 工作量大 | Phase 2 可先做只读摘要，术语/QA 折叠为 Phase 2.1 |
| 检索质量提升不显著 | M3 验收引入"5 题盲测"；不达 30% 提升时下个版本叠加 BM25 混合检索 |
| 异步入库时序 | 复用 [api/meeting.py:_schedule_transcription](../../../backend/tars/api/meeting.py#L266) 模式，避免重新发明轮子 |

---

## 建议执行顺序

```
Week 1: Task 0 (前置·必须) → Task 1–5 (M1) → Task 6–9 (M2)
Week 2: Task 10–12 (M3) → Task 13–14 (M4)
```

> **Task 0 不可跳过：** Provider 注入与异步骨架是 M1 验收的前提，若按原计划同步入库，中等 PDF 会撞超时。

**最小可用版本（MVP）：** 完成 Task 0 + M1 + M2 即可发布 **v4.3.1**；M3/M4 已随 v4.3.1 patch 一并交付（2026-05-25）。

---

## 完成后文档更新

- [x] `docs/01-项目概览/changelog.md` — v4.3.1 知识库深度入库
- [x] `docs/03-实施计划/roadmap.md` — 标记 v4.3.1 知识库项
- [ ] `docs/04-运维文档/` — 新增 `knowledge-deep-ingest-user-guide.md`（用户向：如何浏览摘要、re-enrich）
