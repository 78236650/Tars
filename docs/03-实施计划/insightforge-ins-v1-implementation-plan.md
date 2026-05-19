# InsightForge 鉴数 — 实施计划 INS-1.0.0

> **能力 Tag**: `@insight-forge`  
> **Git 里程碑**: `insight-v1.0.0`  
> **预计总工期**: 3–4 周  
> **依赖**: TARS v4.1.x，`bi` + `knowledge` 已启用  
> **评审**: ✅ 2026-05-19 定稿（Oracle/MySQL/PG/**Doris** + JDBC；`insight_analyst` 不画图；原型 → `python_exec`）

---

## 文档索引

| 文档 | 路径 |
|------|------|
| 产品设计 | `docs/superpowers/specs/2026-05-19-insightforge-design.md` |
| 技术详设 | `docs/02-技术方案/insightforge-ins-v1-design.md` |
| 本计划 | `docs/03-实施计划/insightforge-ins-v1-implementation-plan.md` |

---

## 里程碑

| ID | 版本 | 目标日期 | 交付 |
|----|------|----------|------|
| M0 | INS-1.0.0-rc0 | D+0 | 设计评审通过 |
| M1 | INS-1.0.0-alpha | D+7 | Profile 流水线可用 |
| M2 | INS-1.0.0-beta | D+14 | 指标问答 + Agent 角色 |
| M3 | INS-1.0.0 | D+18 | 工作台 + 导出 + GA |
| M4 | INS-1.0.1 | D+25 | 增量 profile + 压测修复 |

---

## Phase 0 — 脚手架（2 天）

### Task 0.1 模块注册

- [x] `backend/config/modules.yaml` 增加 `insight`
- [x] `ModuleRegistry.OPTIONAL_MODULES` + `requires` 校验
- [x] `main.py` 条件加载 `insight` router
- [x] `tars/insight/version.py` 定义 `INS_VERSION`

### Task 0.2 配置

- [x] `backend/config/insight.yaml` 默认 budget（含 **doris** tier1）
- [x] `InsightConfig` 加载类

### Task 0.3 迁移

- [x] `insight_profile_runs` / `insight_metrics` 表
- [x] `Database` 初始化迁移脚本
- [x] `db_type=doris` + `jdbc` 纳入 BI 数据源校验
- [x] `insight_analyst` 内置角色模板
- [x] `docs/04-运维文档/insightforge-databases.md`

**Commit**: `feat(insight): scaffold InsightForge module INS-1.0.0-alpha`

---

## Phase 1 — 冷启动 Profile（5 天）✅

### Task 1.1 统计与采样

- [x] `sampler.py`
- [x] `stats_collector.py`（**Oracle + MySQL + PostgreSQL + Doris** 方言）
- [x] `dialects/base.py` — Generic / MySQL / PostgreSQL / Oracle
- [x] 单元测试 + SQLite fixture

### Task 1.2 关系与分类

- [x] `relation_inferencer.py`
- [x] `role_classifier.py`

### Task 1.3 流水线与任务

- [x] `profile_pipeline.py` 编排 P1-P5
- [x] `job_runner.py` + progress + 写回 `bi_datasources`
- [x] API: `POST/GET profile`（cancel 待 Phase 1.1）

### Task 1.4 LLM 与发布

- [x] `llm_synthesizer.py` → annotations（无 LLM 时规则回退）
- [x] `knowledge_publisher.py` + 启动时注入 `KnowledgeIndexer`
- [x] `InsightMetricStore.replace_draft_metrics`

**验收**: SQLite 集成测试通过（`test_insight_profile_pipeline.py`）。

**Commit**: `feat(insight): profile pipeline INS-1.0.0-alpha`

---

## Phase 2 — 指标问答（4 天）

### Task 2.1 Metric Store

- [ ] `InsightMetricStore` CRUD
- [ ] profile 写入 `metric_candidates` 为 draft
- [ ] API: metrics list/create/patch approve

### Task 2.2 Metric QA Engine

- [ ] `metric_qa_engine.py`
- [ ] API: `POST /datasources/{id}/ask`
- [ ] 强制回答模板（数值/口径/SQL）

### Task 2.3 Agent 工具与角色

- [ ] `skills/_global/insight_analyst/`
- [ ] tools: `insight_profile_datasource`, `insight_ask_metric`, `insight_explain_metric`
- [ ] `role_template` `insight_analyst` 禁用 `bi_generate_chart` + **`python_exec`**
- [ ] Session `insight_last` 上下文（供 `analyst`/`developer` + `python_exec` 原型）
- [ ] Agent knowledge 过滤 `insight-forge`
- [ ] 文档：鉴数 → 切角色 → `python_exec` 画图的用户指引

**验收**: Chat 使用 `insight_analyst` 问「日 GMV」返数值+SQL，无 chart / python_exec 调用；切 `analyst` 后可基于 `insight_last` 用 python_exec 出原型图。

**Commit**: `feat(insight): metric QA and insight_analyst role INS-1.0.0-beta`

---

## Phase 3 — 前端与导出（3 天）

### Task 3.1 鉴数工作台

- [ ] `InsightView.vue` 路由 `/insight`
- [ ] 数据源列表 + 鉴数按钮 + 进度
- [ ] 指标契约表 + 审批

### Task 3.2 跳转 Chat

- [ ] 带 `datasource_id` + `insight_analyst` 预设

### Task 3.3 导出

- [ ] `exporters.py` → metrics.yaml + glossary.md
- [ ] API `GET /export`

### Task 3.4 i18n

- [ ] `nav.insight` / 鉴数相关文案

**Commit**: `feat(insight): Insight workbench UI INS-1.0.0`

---

## Phase 4 — 加固与发布（3 天）

### Task 4.1 审计

- [ ] `insight_profile`, `insight_ask`, `insight_metric_approve`
- [ ] AuditView 分组 `@insight-forge`

### Task 4.2 测试

- [ ] `test_insight_profile.py`
- [ ] `test_insight_metric_qa.py`
- [ ] `test_insight_security.py`
- [ ] 5 golden questions

### Task 4.3 文档与发布

- [ ] `changelog.md` 增加 **InsightForge INS-1.0.0** 章节
- [ ] `roadmap.md` 业务场景深入阶段条目
- [ ] `docs/04-运维文档/insightforge-databases.md`（Oracle/MySQL/PG/JDBC URL）
- [ ] Git tag `insight-v1.0.0`
- [ ] `vINS-1.0.0-release-notes.md`（可选）

**验收清单（GA）**:

- [ ] 100 表库 20 分钟内 profile 完成或明确跳过原因（**MySQL 或 PG 实测**）
- [ ] **Oracle / Doris** 冒烟：连库 + profile + 1 道指标题
- [ ] **JDBC** 冒烟：generic 模式 profile 不崩溃
- [ ] 5 道指标题 ≥4 准确
- [ ] `insight_analyst` 零 `bi_generate_chart` / `python_exec` 调用
- [ ] `analyst` + `python_exec` 原型路径文档化并通过 1 例 E2E
- [ ] 审计完整

---

## Phase 5 — INS-1.0.1（可选，1 周）

- [ ] 增量 profile（表级 checksum）
- [ ] 值域 overlap 关系 P3
- [ ] 压测报告 + budget 调优

---

## 文件清单（新增/修改）

### 新增

```
backend/tars/insight/**          (~15 files)
backend/config/insight.yaml
backend/migrations/00x_insight_forge.sql
skills/_global/insight_analyst/**
frontend/src/views/InsightView.vue
frontend/src/api/insight.ts
docs/... (已建)
tests/test_insight_*.py
```

### 修改

```
backend/config/modules.yaml
backend/tars/modules/registry.py
backend/tars/main.py
backend/tars/agent/agent.py          # knowledge filter
backend/tars/gateway/role_template.py
frontend/src/router/**
frontend/src/components/layout/LeftPanel.vue
docs/03-实施计划/roadmap.md
docs/01-项目概览/changelog.md
```

---

## 分支策略

```
main
  └── feature/insight-forge-ins-1.0.0
        ├── alpha: profile only
        ├── beta: + metric qa
        └── GA: merge + tag insight-v1.0.0
```

**不 bump TARS 主版本为 5.0**；仅在 changelog 记录「搭载 INS-1.0.0」。

---

## 风险缓冲

| 风险 | 缓冲天 |
|------|--------|
| LLM JSON 不稳定 | +2 |
| 方言 SQL 差异 | +2 |
| 前端进度 UX | +1 |

---

*执行时按 Task checkbox 更新；完成后打 Git tag `insight-v1.0.0`。*
