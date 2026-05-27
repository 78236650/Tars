---
doc_type: plan
status: shipped
platform_version: 4.2.0
catalog: docs/superpowers/README.md
---
# InsightForge INS-2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 InsightForge 从 INS-1.0「鉴数工作台 + 规划中的问数」升级为 **INS-2.0 对话优先 Copilot**：统一 Workflow、Metric QA、Chat 问数卡片、W1 运维台，并满足 GA 评测与部署约束。

**Architecture:** 以 `InsightWorkflowService` 为唯一状态中枢（数据源级 + 会话级双层 state）；`MetricQaEngine` 负责问数路由与执行；Chat/W1 为门面。M2 先交付 ask 能力，M3 再改 UI，避免半瘫痪窗口。特性开关 `insight.chat_first_enabled` 控制灰度。

**Tech Stack:** Python 3.11+, FastAPI, Vue 3 + TypeScript, SQLite, 现有 `bi` + `knowledge` + SQLAlchemy；SSE；pytest + `pytest -m insight_eval`

**规格:** [`docs/superpowers/specs/2026-05-20-insightforge-ins-2-redesign.md`](../specs/2026-05-20-insightforge-ins-2-redesign.md)

**前置:** INS-1.0 Profile 流水线已落地（`profile_pipeline.py`、`/profile` API、`InsightView` 初版）

**Git 里程碑:** `insight-v2.0.0` · 版本常量 `INS-2.0.0`

**预计工期:** 约 4–5 周（M1–M5）

---

## 里程碑总览

| 阶段 | 版本 | 工期 | 交付 | 上线影响 |
|------|------|------|------|----------|
| **M1** | INS-2.0.0-alpha | ~5d | Workflow 后端 + 迁移 + API | 无 UI 变化 |
| **M2** | INS-2.0.0-beta | ~7d | MetricQa + `/ask` + Chat 卡片 + eval_set | 问数可用 |
| **M3** | INS-2.0.0-rc | ~4d | WorkflowStrip + W1 瘦身 | Chat 主战场 |
| **M4** | INS-2.0.0-rc2 | ~5d | adopt + 工具 + `insight_analyst` + feedback | 治理闭环 |
| **M5** | INS-2.0.0 | ~3d | GA、admin LLM、文档、部署注释 | GA |

---

## 文件结构（INS-2.0 增量）

```
backend/
  config/insight.yaml                          # [EXTEND] forge/qa/feedback/adoption 配置
  tars/insight/
    version.py                                 # [MOD] INS-2.0.0
    workflow_service.py                          # [NEW]
    workflow_context.py                          # [NEW]
    workflow_events.py                           # [NEW] 进程内 SSE 环形缓冲
    metric_qa_engine.py                          # [NEW]
    question_log_store.py                        # [NEW]
    adoption_service.py                          # [NEW] adopt + H3 降级
    store.py                                     # [EXTEND] metrics CRUD/adopt/version
    profile_pipeline.py                          # [MOD] 写 workflow.state + ins_version
    job_runner.py                                # [MOD] 发布 workflow 事件 + pending_question
    config.py                                    # [MOD] 新配置段
    api/router.py                                # [EXTEND] workflow/ask/adopt/SSE/forge 别名
    tools/                                       # [NEW] Agent 工具模块
  tars/database/base.py                          # [MOD] sessions.metadata_json + 新表迁移
  tars/gateway/role_template.py                  # [MOD] insight_analyst tools
  tests/
    test_insight_workflow.py                     # [NEW]
    test_insight_metric_qa.py                    # [NEW]
    test_insight_adopt.py                        # [NEW]
    insight/eval_set.yaml                        # [NEW] H8
    insight/test_insight_eval.py                 # [NEW] pytest -m insight_eval

frontend/src/
  api/index.ts                                 # [EXTEND] workflow/ask/feedback
  components/insight/WorkflowStrip.vue           # [NEW]
  components/insight/MetricAnswerCard.vue      # [NEW]
  components/insight/SchemaPreviewDrawer.vue   # [NEW] 消费 /brief
  views/InsightView.vue                          # [MOD] W1 运维台
  views/ChatView.vue                             # [MOD] strip + 卡片
  components/chat/ChatPanel.vue                  # [MOD] 集成
  i18n/index.ts                                  # [EXTEND]
  router/index.ts                                # [MOD] 可选 /admin/insight/llm M5

docs/
  03-实施计划/insightforge-ins-v2-implementation-plan.md  # 本计划副本索引
  04-运维文档/insightforge-deploy.md             # [NEW] H1 workers/sticky
```

---

## Phase M1 — Workflow 中枢（后端 only，~5 天）

> **验收:** `GET /workflow` 返回合成状态；`POST /forge` 与 `/profile` 等价；迁移后旧数据源 `ready`/`needs_forge` 正确；**不修改** InsightView 主流程。

### Task M1.1: 版本与配置

**Files:**
- Modify: `backend/tars/insight/version.py`
- Modify: `backend/config/insight.yaml`
- Modify: `backend/tars/insight/config.py`

- [ ] **Step 1:** `INS_VERSION = "INS-2.0.0"`，`INS_API_VERSION = 2`
- [ ] **Step 2:** `insight.yaml` 增加：

```yaml
forge:
  pending_question_ttl_seconds: 1800
qa:
  fewshot_max_items: 5
  fewshot_max_tokens: 2000
  fewshot_recall_timeout_ms: 200
  allow_ad_hoc_sql: true
adoption:
  require_review: false
feedback:
  downgrade_window_days: 30
  downgrade_min_down: 3
  downgrade_ratio_min: 0.30
  downgrade_cooldown_days: 7
feature_flags:
  chat_first_enabled: false
```

- [ ] **Step 3:** `InsightConfig` 解析上述字段；`get_insight_config()` 单例不变
- [ ] **Step 4:** Commit `chore(insight): bump INS-2.0.0 config scaffold`

---

### Task M1.2: 数据库迁移

**Files:**
- Modify: `backend/tars/database/base.py`
- Create: `backend/tests/test_insight_workflow_migration.py`

- [ ] **Step 1: 写失败测试 — sessions 含 metadata_json**

```python
def test_sessions_has_metadata_json_column(db):
    row = db._get_conn().execute("PRAGMA table_info(sessions)").fetchall()
    cols = {r[1] for r in row}
    assert "metadata_json" in cols
```

- [ ] **Step 2:** 运行确认 FAIL

Run: `cd backend && pytest tests/test_insight_workflow_migration.py::test_sessions_has_metadata_json_column -v`

- [ ] **Step 3:** 在 `Database._init_schema` 中：

```python
try:
    cursor.execute("ALTER TABLE sessions ADD COLUMN metadata_json TEXT DEFAULT '{}'")
except sqlite3.OperationalError:
    pass
```

- [ ] **Step 4:** 新增表（若不存在）`insight_question_log`、`insight_metric_adoptions`（schema 见 spec §10.2）
- [ ] **Step 5:** `insight_metrics` 增 `version INTEGER DEFAULT 1`、`superseded_by TEXT`；唯一索引 `idx_insight_metrics_key_ver`
- [ ] **Step 6:** 回填脚本函数 `backfill_insight_workflow_states(db)`：有 completed run → `ready`，否则 `needs_forge`
- [ ] **Step 7:** 测试 PASS；Commit `feat(insight): INS-2.0 schema migration`

---

### Task M1.3: InsightWorkflowService

**Files:**
- Create: `backend/tars/insight/workflow_service.py`
- Create: `backend/tars/insight/workflow_context.py`
- Test: `backend/tests/test_insight_workflow.py`

- [ ] **Step 1: 写失败测试 — show_workflow_strip**

```python
def test_show_workflow_strip_needs_forge():
    assert show_workflow_strip("needs_forge", "idle") is True

def test_show_workflow_strip_ready_idle():
    assert show_workflow_strip("ready", "idle") is False

def test_show_workflow_strip_no_source():
    assert show_workflow_strip("ready", "no_source") is True
```

- [ ] **Step 2:** 实现 `show_workflow_strip(datasource_state, session_state) -> bool`（spec §3.1.3）
- [ ] **Step 3:** 实现 `InsightWorkflowService`：
  - `get_composite(datasource_id, tenant_id, session_id) -> dict`
  - `get_llm_context_bundle(...) -> dict`（§五字段）
  - `set_datasource_state(ds_id, tenant_id, state, **kwargs)`
  - `get_session_insight(session_id) / patch_session_insight(session_id, patch)` — 读写 `sessions.metadata_json.insight`
  - **H2:** 同步 ask 路径不设置 `asking`；仅预留 `set_session_asking_for_stream(session_id, bool)`
- [ ] **Step 4:** `transition_on_profile_complete(run_id)` → `ready`；检查 `pending_question` + **H5** TTL（从 `ready_at` 起算）
- [ ] **Step 5:** 测试 PASS
- [ ] **Step 6:** Commit `feat(insight): InsightWorkflowService INS-2.0`

---

### Task M1.4: Workflow API + forge 别名

**Files:**
- Modify: `backend/tars/insight/api/router.py`
- Modify: `backend/tars/insight/profile_pipeline.py`（完成时调 workflow transition）
- Modify: `backend/tars/insight/job_runner.py`

- [ ] **Step 1:** `GET /datasources/{id}/workflow?session_id=` → 合成 JSON + `show_workflow_strip`
- [ ] **Step 2:** `POST /datasources/{id}/forge` 启动 profile（复用现有 `start_profile` 逻辑）
- [ ] **Step 3:** `POST /datasources/{id}/profile` → 内部转发 `forge`（R5）
- [ ] **Step 4:** `/version` 的 `phase` 增加 `workflow: true`；`INS_VERSION` 2.0.0
- [ ] **Step 5:** 集成测试 `test_insight_workflow_api_roundtrip`（fixture 数据源）
- [ ] **Step 6:** Commit `feat(insight): workflow API M1`

---

### Task M1.5: SSE 事件缓冲（R6 + H1 文档）

**Files:**
- Create: `backend/tars/insight/workflow_events.py`
- Modify: `backend/tars/insight/api/router.py`
- Create: `docs/04-运维文档/insightforge-deploy.md`

- [ ] **Step 1:** `ForgeEventBus`：进程内 `dict[run_id, deque]`，max 100；`publish(run_id, event_type, data)` 分配单调 `id`
- [ ] **Step 2:** `GET /datasources/{id}/forge/events` SSE（§7.1 事件类型 + heartbeat 30s）
- [ ] **Step 3:** 支持 `Last-Event-ID` 补发；超 50 连接返回 429
- [ ] **Step 4:** `insightforge-deploy.md` 写明 **H1**: `uvicorn --workers 1` 或 sticky session
- [ ] **Step 5:** Commit `feat(insight): forge SSE events`

**M1 里程碑验收:** 旧 W1 仍可用；`curl GET /workflow` 正确；profile 完成后 `datasource_state=ready`。

---

## Phase M2 — Metric QA + Chat 问数（~7 天）

> **验收:** `POST /ask` 返回 `MetricAnswer`；Chat 展示卡片；`eval_set.yaml` 存在且 `pytest -m insight_eval` 可跑（允许初始未达 80%）。

### Task M2.1: Question log store

**Files:**
- Create: `backend/tars/insight/question_log_store.py`
- Test: `backend/tests/test_insight_metric_qa.py`

- [ ] **Step 1:** `insert_log(...)` / `list_fewshot_candidates(datasource_id, tenant_id, limit=20)`
- [ ] **Step 2:** **H4:** `select_for_prompt(candidates, max_items=5, max_tokens=2000)`；超时 200ms 返回 `[]`
- [ ] **Step 3:** 单元测试 token 裁剪与超时跳过

---

### Task M2.2: MetricQaEngine

**Files:**
- Create: `backend/tars/insight/metric_qa_engine.py`
- Extend: `backend/tars/insight/store.py`（`get_by_key`, `list_approved`）
- Test: `backend/tests/test_insight_metric_qa.py`

- [ ] **Step 1: 写失败测试 — hit_approved 填参不改 SQL 模板**

```python
@pytest.mark.asyncio
async def test_hit_approved_fills_params_only(engine, approved_metric):
    ans = await engine.ask(ds_id, tenant_id, "昨日 GMV", candidate_metric_keys=None)
    assert ans.branch == "hit_approved"
    assert ans.caliber_tier == "official"
    assert "SUM" in ans.sql.upper()
```

- [ ] **Step 2:** 实现路由分支（§6.1）：KB + metrics + few-shot → LLM JSON → 分支执行
- [ ] **Step 3:** **H6:** `hit_partial` 返回 `candidates`；二轮带 `candidate_metric_keys`；仍 partial → adhoc/rejected
- [ ] **Step 4:** `SQLSecurityChecker` + 只读执行；组装 `MetricAnswer`（含 `as_of`, `lag_seconds`, `confidence`, `branch`）
- [ ] **Step 5:** `needs_forge` → 抛 `INSIGHT_NOT_PROFILED`；`forging` → `INSIGHT_WORKFLOW_BLOCKED`
- [ ] **Step 6:** 每次 ask 写 `insight_question_log`
- [ ] **Step 7:** Commit `feat(insight): MetricQaEngine`

---

### Task M2.3: Ask API

**Files:**
- Modify: `backend/tars/insight/api/router.py`

- [ ] **Step 1:** Pydantic `AskMetricRequest` / `MetricAnswer` 响应模型（含 `candidates?: list[str]`）
- [ ] **Step 2:** `POST /datasources/{id}/ask` — **不写** session `asking`（H2）
- [ ] **Step 3:** `POST /datasources/{id}/ask/stream` — 流式可选；**可**设置 `asking`
- [ ] **Step 4:** 审计 `insight_ask` + `caliber_tier` + `branch`
- [ ] **Step 5:** 集成测试：SQLite fixture 库 + mock LLM 路由 JSON

---

### Task M2.4: eval_set（H8）

**Files:**
- Create: `backend/tests/insight/eval_set.yaml`
- Create: `backend/tests/insight/test_insight_eval.py`
- Modify: `backend/pyproject.toml` 或 `pytest.ini` — marker `insight_eval`

- [ ] **Step 1:** `eval_set.yaml` ≥10 条，覆盖 `hit_approved|hit_draft|adhoc|hit_partial|miss`
- [ ] **Step 2:** `test_insight_eval.py` 加载 yaml，对每条调用 `MetricQaEngine`（或 HTTP 黑盒），断言 `expected_branch` + 数值容差
- [ ] **Step 3:** `pytest -m insight_eval` 注册；CI job 可选非阻塞
- [ ] **Step 4:** Commit `test(insight): eval_set baseline`

---

### Task M2.5: 前端 MetricAnswerCard + Chat 集成

**Files:**
- Create: `frontend/src/components/insight/MetricAnswerCard.vue`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/components/chat/ChatPanel.vue`

- [ ] **Step 1:** `insightApi.ask(datasourceId, { question, candidate_metric_keys?, as_of_date? })`
- [ ] **Step 2:** `MetricAnswerCard` 四块布局 + 档级徽章 + 👍👎（feedback API 可先 stub M4）
- [ ] **Step 3:** Chat 识别 assistant 消息中 `type: 'insight_metric_answer'` 或 API 直出卡片数据
- [ ] **Step 4:** **H6:** partial 卡片展示 `candidates` + 澄清后自动带 `candidate_metric_keys` 重问
- [ ] **Step 5:** `phase.metric_qa_in_chat: true` 时显示入口
- [ ] **Step 6:** Commit `feat(insight-ui): MetricAnswerCard + ask`

**M2 里程碑验收:** 在 Chat 对已完成 profile 的数据源问数可见卡片；eval 可运行。

---

## Phase M3 — WorkflowStrip + W1 瘦身（~4 天）

> **验收:** V2 阻塞条；W1 无 LLM 主面板；Schema 抽屉用 `/brief`（H7）。

### Task M3.1: WorkflowStrip.vue

**Files:**
- Create: `frontend/src/components/insight/WorkflowStrip.vue`
- Modify: `frontend/src/views/ChatView.vue` 或 `ChatPanel.vue`

- [ ] **Step 1:** `insightApi.getWorkflow(datasourceId, sessionId)` 轮询或 SSE 联动
- [ ] **Step 2:** `show_workflow_strip` 为 true 时渲染步骤条 + CTA（鉴数 / 鉴数并接续 **H5**）
- [ ] **Step 3:** `forging` 显示 phase%；`forge_failed` 显示错误+重试
- [ ] **Step 4:** `ready` 后隐藏条（V2）

---

### Task M3.2: W1 运维台瘦身

**Files:**
- Modify: `frontend/src/views/InsightView.vue`
- Create: `frontend/src/components/insight/SchemaPreviewDrawer.vue`

- [ ] **Step 1:** 删除 LLM `<details>` 主面板（保留数据表 `insight_llm_settings`）
- [ ] **Step 2:** 移除表注解大列表、关系长列表；保留进度/重试/计数
- [ ] **Step 3:** **H7:** `SchemaPreviewDrawer` 仅 `GET /brief` 裁剪展示
- [ ] **Step 4:** 副标题「数据源运维」；首次打开迁移提示
- [ ] **Step 5:** `workbench: 'ops_only'` phase 旗标
- [ ] **Step 6:** Commit `feat(insight-ui): W1 ops console M3`

**M3 门禁:** M2 ask 已在预发稳定 ≥7 天（或团队 sign-off）后再全量开 `chat_first_enabled`。

---

## Phase M4 — 治理闭环（~5 天）

### Task M4.1: Adoption + feedback

**Files:**
- Create: `backend/tars/insight/adoption_service.py`
- Modify: `backend/tars/insight/store.py`
- Modify: `backend/tars/insight/api/router.py`

- [ ] **Step 1:** `POST /metrics/{id}/adopt` — 默认 `require_review=false` 直采；true 时写 `insight_metric_adoptions`
- [ ] **Step 2:** **H3:** `POST /ask/{question_log_id}/feedback` 更新 feedback；触发降级评估（30d 窗口 + 30% + 7d cooldown）
- [ ] **Step 3:** 并发 adopt 409 `INSIGHT_ADOPTION_CONFLICT`；metric `version` bump（§4.1.2）
- [ ] **Step 4:** 测试 `test_insight_adopt.py`

---

### Task M4.2: Agent 工具 + insight_analyst

**Files:**
- Create: `backend/tars/insight/tools/*.py`（注册到 Agent 工具表）
- Modify: `backend/tars/gateway/role_template.py`
- Create: `skills/_global/insight_analyst/SKILL.md`（若项目用 skills 目录）

- [ ] **Step 1:** 工具：`insight_get_workflow`, `insight_start_forge`, `insight_profile_datasource`, `insight_list_sources`, `insight_ask_metric`, `insight_adopt_metric`, `insight_explain_metric`, `insight_give_feedback`
- [ ] **Step 2:** `insight_analyst` allowed_tools 更新；denied 保持无 chart/python
- [ ] **Step 3:** system prompt 注入 `insight_workflow` bundle + §1.4 路由约束
- [ ] **Step 4:** 问数成功写 session/agent `insight_last`（sql, result, metric_key）
- [ ] **Step 5:** E2E：Chat 角色 `insight_analyst` 问数 → 采用，无 `bi_generate_chart` 调用

---

### Task M4.3: pending_question 自动接续（H5）

**Files:**
- Modify: `backend/tars/insight/workflow_service.py`
- Modify: `backend/tars/insight/job_runner.py`

- [ ] **Step 1:** `start_forge` body 可选 `pending_question` + `session_id`
- [ ] **Step 2:** profile `completed` 时若 TTL 内则自动调用 `MetricQaEngine.ask`
- [ ] **Step 3:** 测试：mock profile 完成 → 自动 ask 被调用一次

**M4 里程碑验收:** GA 清单中 adopt、feedback、analyst、eval ≥80%（迭代 yaml 直至通过）。

---

## Phase M5 — GA（~3 天）

### Task M5.1: Admin LLM + 清理

**Files:**
- Create: `frontend/src/views/admin/InsightLlmAdminView.vue`（或合入现有 admin 路由）
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1:** `/admin/insight/llm` 仅 `tenant_admin`；迁移原 W1 LLM 配置能力
- [ ] **Step 2:** 删除 InsightView 死代码与 INS-1 phase 提示文案
- [ ] **Step 3:** 评估 deprecate `POST /profile` 别名（保留至少一版）

---

### Task M5.2: 文档与发布

**Files:**
- Modify: `docs/01-项目概览/changelog.md`
- Modify: `docs/03-实施计划/roadmap.md`
- Modify: `backend/config/modules.yaml` — `version: INS-2.0.0`

- [ ] **Step 1:** Changelog「InsightForge INS-2.0.0」小节
- [ ] **Step 2:** 默认 `feature_flags.chat_first_enabled: true`（或环境变量覆盖）
- [ ] **Step 3:** Git tag `insight-v2.0.0`
- [ ] **Step 4:** GA checklist（spec §十二）逐项勾选

---

## 跨模块改动清单

| 模块 | M1 | M2 | M3 | M4 | M5 |
|------|----|----|----|----|-----|
| `insight/*` | ● | ● | ● | ● | ● |
| `database/base.py` | ● | | | | |
| `api/sessions` metadata | ● | | ● | ● | |
| `gateway/role_template` | | | | ● | |
| `frontend Chat` | | ● | ● | ● | |
| `frontend InsightView` | | | ● | | ● |
| `bi`（只读调用） | | ● | | ● | |
| `knowledge` | | ● | | | |
| `meeting/skillhub` | | | | | |

---

## Spec 覆盖自检

| Spec 章节 | 任务 |
|-----------|------|
| §3 双层 state + V2 strip | M1.3, M3.1 |
| §3.3.1 pending_question H5 | M1.3, M4.3 |
| §4.1 adopt / H3 降级 | M4.1 |
| §6 MetricQa + H4/H6 | M2.2–M2.5 |
| §7 API + SSE H1/R5/H7/H9 | M1.4–M1.5, M2.3 |
| §8 工具与 analyst | M4.2 |
| §9 W1 + Chat | M2.5, M3 |
| §10 迁移 | M1.2 |
| §11 审计 | M2.3, M4.1 |
| §12 GA + H8 eval | M2.4, M4–M5 |
| §1.4 bi_query 约束 | M4.2 prompt |

---

## 执行方式（完成后选用）

**Plan 路径:** `docs/superpowers/plans/2026-05-20-insightforge-ins-2-implementation-plan.md`

1. **Subagent-Driven（推荐）** — 每 Task 独立 subagent + 两阶段 review（`subagent-driven-development`）
2. **Inline Execution** — 本会话按 M1→M5 连续执行（`executing-plans`），每阶段 checkpoint

建议 isolated worktree：`feature/insight-forge-ins-2.0.0`。
