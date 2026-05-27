---
doc_type: spec
status: shipped
platform_version: 4.2.0
catalog: docs/superpowers/README.md
---
# Phase 1：内网数据/分析 Copilot — 设计说明

> **文档日期**: 2026-05-24  
> **目标版本**: TARS **v4.2.0** "Data Copilot & Evolution"  
> **状态**: ✅ Phase 1 设计已批准（2026-05-24）  
> **方案**: 方案 2 — Insight 知识桥接层

---

## 一、目标与范围

### 1.1 产品目标

在内网试点场景交付 **分模块入口的数据/分析 Copilot**：

| 用户群 | 占比 | 主路径 | 模块 |
|--------|------|--------|------|
| 业务方 | ~80% | Chat（通用）→ `/insight` 问数/口径/采用 | insight + knowledge |
| 数据工程师 | ~20% | `/bi` SQL/Schema/图表；必要时 `/insight` | bi + insight + knowledge |

**共同价值**：问数回答引用会议/文档/鉴数说明书；采用官方口径可回写知识库；文档可标注关联指标。

### 1.2 In Scope

- **A** InsightForge 生产化：部署约束、模块 gating 接通、角色默认模块
- **B** BI ↔ Insight 边界：文档 + 导航文案 + 验收脚本
- **C** 知识联动 B+C：口径优先检索 + 采用↔文档双向关联

### 1.3 Out of Scope（Phase 1 不做）

- 统一 Copilot 首页 / Chat 智能意图路由
- 报表设计器 / 看板
- SSO / SAML / OIDC
- 统一向量索引（Profile + KB 合并）
- Evolution、多通道、桌面端

### 1.4 验收标准

| # | 类型 | 验收项 |
|---|------|--------|
| 1 | 流程 | 业务账号：Chat → `/insight` 全流程，不打开 BI |
| 2 | 流程 | 工程师账号：可独立使用 `/bi` |
| 3 | 流程 | 问数回答含 ≥1 条 `[ref:doc_id]` 知识引用 |
| 4 | 技术 | 业务角色 gating：可见 insight + knowledge，默认不可见 bi |
| 5 | 技术 | SSE 在 workers=1 或 sticky 环境稳定 |
| 6 | 技术 | 集成测试：KB chunk → MetricQa citations 链路 |
| 7 | 质量 | `pytest -m insight_eval` ≥80%（原 10 题） |
| 8 | 质量 | 新增 3–5 eval 用例：会议摘要/口径文档影响问数 |

---

## 二、架构与组件

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Vue 3)                                            │
│  App.vue → initSettings() [modules + roleModules]           │
│  LeftPanel → 模块导航 + 角色/全局 gating                     │
│  InsightView / Chat WorkflowStrip / MetricAnswerCard        │
│  KnowledgeCitationPanel（复用 Chat 引用卡片）                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ InsightForge (INS-2.0)                                      │
│  MetricQaEngine.ask()                                       │
│    └─ KnowledgeBridge.retrieve_for_question()  [新增]       │
│  AdoptionService.adopt()                                    │
│    └─ KnowledgeBridge.publish_metric_card()     [新增]      │
│  KnowledgePublisher（已有，鉴数说明书发布）                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ Knowledge Layer                                           │
│  knowledge/access.py — search_knowledge(tenant, query, …)  │
│  Collections 优先级:                                        │
│    1. insight_{datasource_id}                               │
│    2. meeting_* / 会议摘要 collection（按 tenant 配置）      │
│    3. 含 metadata.metric_ids 的通用文档                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 新增/修改组件

| 组件 | 路径 | 职责 |
|------|------|------|
| **KnowledgeBridge** | `backend/tars/insight/knowledge_bridge.py` | 问数前分层检索；采用后写 metric card；解析 metric_ids |
| **MetricCitation** | `backend/tars/insight/metric_answer.py` | dataclass：`doc_id`, `title`, `snippet`, `source_type`, `relevance` |
| **MetricAnswer.citations** | 同上 | 扩展字段，API/WS 序列化 |
| **business_analyst 角色** | `backend/tars/gateway/role_template.py` | 业务默认：insight + knowledge + meeting，无 bi |
| **initSettings 接通** | `frontend/src/App.vue` | 登录后 loadModules + loadRoleModules |
| **RoleEditor insight** | `frontend/src/components/settings/RoleEditor.vue` | 模块列表补 `insight` |
| **LeftPanel 文案** | `frontend/src/components/layout/LeftPanel.vue` | 模块 subtitle：业务→Insight，工程师→BI |
| **部署检查** | `backend/tars/insight/api/router.py` 或 startup | SSE workers 警告日志 |

### 2.3 角色与模块矩阵（Phase 1 默认）

| 角色 | allowed_modules | 说明 |
|------|-----------------|------|
| **business_analyst**（新增） | insight, knowledge, meeting, skillhub | 80% 业务用户默认 |
| insight_analyst | insight, knowledge | 去掉 bi（当前含 bi，需调整） |
| analyst | bi, knowledge, insight | 20% 工程师 |
| developer | bi, knowledge, insight, meeting, skillhub | 全栈工程师 |
| standard | 迁移：加 insight，移除 bi | 或弃用，改分配 business_analyst |
| admin | * | 不变 |

**迁移策略**：新用户默认 `business_analyst`；现有 `standard` 用户批量脚本可选迁移（不强制）。

### 2.4 BI vs Insight 边界（B）

| 场景 | 入口 | 工具/能力 |
|------|------|-----------|
| 「上月 GMV 多少？」「口径是什么？」 | `/insight` 或 Chat + insight_analyst | MetricQaEngine, insight_* tools |
| 「写 SQL 查订单明细」「画趋势图」 | `/bi` | bi_query, bi_generate_chart |
| 「会议里定的指标定义」 | 知识库 + Insight 问数引用 | KnowledgeBridge |
| Chat 通用对话 | `/` | 通用 Agent，不自动路由到 BI/Insight |

文档输出：`docs/04-运维文档/data-copilot-user-guide.md`（业务/工程师分节）。

---

## 三、数据流

### 3.1 问数 + 知识引用（B 口径优先）

```
User question
  → MetricQaEngine.ask()
  → KnowledgeBridge.retrieve_for_question(tenant_id, datasource_id, question)
       Step 1: search collection insight_{datasource_id}, top_k=3
       Step 2: search meeting/summary collections (tenant config), top_k=2
       Step 3: search docs where metadata.metric_ids contains matched metric_key, top_k=2
       Merge + dedupe by doc_id, cap total tokens ≤1500
  → Inject into LLM context (definition/reasoning branch only, not SQL generation for official tier)
  → MetricAnswer { ..., citations: [MetricCitation, ...] }
  → Frontend MetricAnswerCard renders [ref:doc_id|title] chips → KnowledgeCitationPanel
```

**约束**：
- `caliber_tier=official` 时 SQL 仅来自 `insight_metrics`，知识仅用于 definition/reasoning 解释
- `suggested/adhoc` 可在 reasoning 中引用知识，不改变 SQL 安全校验

### 3.2 采用口径 → 知识库（C 双向闭环）

```
AdoptionService.adopt(metric_id, ...)
  → metric_store.adopt_metric() [existing]
  → if config.adoption.publish_to_knowledge != false:
       KnowledgeBridge.publish_metric_card(
         datasource_id, metric, tenant_id
       )
       → append/update markdown section in insight_{datasource_id}
       → re-index via knowledge_indexer
       → documents.metadata_json.metric_ids += [metric.id]
```

**文档侧关联**（上传/API）：
- `POST /api/knowledge/.../documents` 接受可选 `metric_ids: string[]`
- 存入 `documents.metadata_json`
- KnowledgeBridge Step 3 检索时使用

### 3.3 模块 Gating 数据流

```
App mount
  → authStore.initAuth()
  → settingsStore.initSettings()
       → loadModules() → GET /api/modules → enabledModules
       → loadRoleModules() → GET /api/roles/users/{id}/permissions → roleAllowedModules
  → router.beforeEach: block route if module not in both lists
  → LeftPanel: filter nav items
```

---

## 四、错误处理

| 场景 | 行为 |
|------|------|
| 知识检索超时（>500ms） | 跳过知识注入，问数照常；`citations=[]`；日志 warn |
| 知识库模块 disabled | KnowledgeBridge 返回空，不 fail ask |
| insight collection 不存在 | 跳过 Step 1，继续 Step 2/3 |
| publish_metric_card 失败 | adopt 仍成功；audit 记 `knowledge_publish_failed` |
| SSE 多 worker 无 sticky | startup 打 ERROR 日志 + deploy doc 链接 |
| 业务用户访问 /bi | 403 或 router redirect `/` + toast |

---

## 五、测试计划

### 5.1 单元/集成

| 测试文件 | 覆盖 |
|----------|------|
| `test_insight_knowledge_bridge.py` | 分层检索优先级、dedupe、token cap |
| `test_insight_adopt_knowledge.py` | adopt → metric card 写入 |
| `test_role_module_gating.py` | business_analyst 无 bi |
| `frontend/router/index.spec.ts` | insight 路由 + gating |

### 5.2 Eval 扩展

在 `backend/tests/insight/eval_set.yaml` 新增 3–5 题，例如：

1. 会议摘要含「GMV=不含退款订单金额」→ 问 GMV 口径 → citations 含会议 doc
2. 鉴数说明书含表关系 → 问某指标 → citations 含 insight_{ds} doc
3. 已 adopt 指标 → 问数值 → caliber_tier=official + citation 含 metric card

门槛：全量 ≥80%。

### 5.3 手动验收脚本

`scripts/acceptance/phase1-data-copilot.sh`：
- 业务 token：/insight workflow E2E
- 工程师 token：/bi query
- 问数响应 JSON 含 `citations.length >= 1`

---

## 六、实施顺序（供 writing-plans 使用）

| 序号 | 工作包 | 预估 |
|------|--------|------|
| W1 | `initSettings` + RoleEditor insight + business_analyst 角色 | 1d |
| W2 | 部署检查 + data-copilot-user-guide.md | 0.5d |
| W3 | KnowledgeBridge + MetricAnswer.citations | 2d |
| W4 | AdoptionService 挂钩 publish_metric_card | 1d |
| W5 | 文档 metadata metric_ids + API | 1d |
| W6 | MetricAnswerCard citations UI | 1d |
| W7 | eval 扩展 + 集成测试 + acceptance 脚本 | 1.5d |

**合计**：约 8 人日。

---

## 七、风险与缓解

| 风险 | 缓解 |
|------|------|
| standard 角色已有 bi 无 insight，与 80% 业务假设冲突 | 新增 business_analyst，文档说明迁移 |
| 知识检索增加 ask 延迟 | 500ms 超时跳过；异步 prefetch 留 Phase 1.1 |
| insight_analyst 角色仍含 bi 模块 | 调整为仅 insight + knowledge |
| 前端 gating fail-open（enabledModules=[]） | initSettings 必须在 auth 后调用 |

---

*Phase 1 设计评审通过后，进入 writing-plans 生成实施计划；随后 Phase 2（自进化）头脑风暴。*
