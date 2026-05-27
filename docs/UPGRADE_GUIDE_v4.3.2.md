# TARS v4.3.2 — 升级指南（Superpowers + Wiki）

> 版本对照：[01-项目概览/VERSION.md](./01-项目概览/VERSION.md)  
> 基于 **v4.3.1** patch；Git 开发分支 **`v4.3.2`**（见 [VERSION.md](./01-项目概览/VERSION.md)）。

## 概述

v4.3.2 在 v4.3.1 基础上新增：

1. **Superpowers**（可选开关）— Skill 路由、Plan 门控、Verification Gate  
2. **Wiki + RAG 双通路**（随知识库模块）— `read_wiki` / `write_wiki`、知识库 Wiki Tab

Superpowers 三项均可通过 `backend/config/modules.yaml` 独立开关：

| 能力 | 配置键 | 作用 |
|------|--------|------|
| Skill 自动路由 | `skill_routing.enabled` | 根据 `triggers` / embedding 推荐技能 |
| Plan 审批门控 | `plan_gate.enabled` | 复杂计划需用户批准后再执行 |
| Verification Gate | `verification.enabled` | 计划完成后跑 verify 命令，失败不标 done |

## 升级步骤

### 1. 拉取代码并安装依赖

无新增 Python 依赖。前端需包含 `PlanReviewDialog` 组件（已内置）。

### 2. 更新配置

编辑 `backend/config/modules.yaml`：

```yaml
skill_routing:
  enabled: true

plan_gate:
  enabled: true
  always_approve: false
  auto_approve_threshold: 3
  review_timeout_sec: 600
  reminder_at_sec: 300
  fallback_auto_approve: true

verification:
  enabled: true
  default_mode: strict
  lenient_pass_rate: 0.8
  fail_action: rollback
```

路由细项见 `backend/config/skills.yaml` 的 `router` 段（`use_embedding`、`top_k`、`min_score`）。

### 3. 为 Skill 补充元数据（可选但推荐）

在 `SKILL.md` frontmatter 增加：

```yaml
triggers:
  - "查询数据"
  - "intent:data.analyze"
skip_when:
  - "解释.*代码"
priority: 80
verify_mode: strict
verify:
  - command: "echo ok"
    expect: 'stdout contains "ok"'
    timeout_sec: 10
```

详见 [SKILL_AUTHORING.md](./SKILL_AUTHORING.md)。

### 4. 重启服务

```bash
cd backend && uvicorn tars.main:app --reload
cd frontend && npm run dev
```

## 行为变化

### Skill 路由

- Agent 在 system prompt 中收到 **推荐技能 (Router)** 区块
- Router 只推荐，LLM 保留最终是否采用的决定权
- 旧 skill 无 `triggers` 时仍走 v2.2 的 `trigger_intents` / 内容匹配
- 路由推荐/采纳写入 `skill_routing_events`，Evolution `SkillOptimizer` 可据此建议收紧 triggers

### Plan 门控

| 条件 | 行为 |
|------|------|
| steps < 3 且无危险工具 | 自动批准 |
| steps ≥ 3 且含 shell/file_write/network | 必须审批 |
| steps ≥ 5 | 必须审批 |
| 无 WebSocket 连接 | `fallback_auto_approve: true` 时自动批准 |

WebSocket 事件：`plan_review_request`、`plan_review_reminder`、`plan_review_cancelled`。

REST API：

- `GET /api/plans` / `GET /api/plans/{id}`
- `POST /api/plans/{id}/approve`（可带修改后的 steps）
- `POST /api/plans/{id}/reject`
- `POST /api/plans/{id}/retry` — 从最近 checkpoint 后台恢复执行（需 WebSocket 在线以接收进度事件）

### Verification Gate

- 计划步骤全部成功后，若关联 skill（如 `skill://deploy/...`）声明了 `verify`，则逐条执行
- 失败 → 计划状态 `failed`，WebSocket 推送 `verification_failed`
- 结果写入 `verification_audit` 表，可通过 `GET /api/plans/{id}/verification` 查询

## 回滚

将对应 `enabled: false` 即可恢复 v4.3.1 行为，无需删库：

```yaml
skill_routing:
  enabled: false
plan_gate:
  enabled: false
verification:
  enabled: false
```

## 测试

```bash
cd backend
pytest tests/test_skill_router.py tests/test_skill_routing_e2e.py \
       tests/test_plan_gate_e2e.py tests/test_verification_gate.py \
       tests/test_plan_retry_e2e.py tests/test_superpowers_v432_e2e.py -q

# Skill 路由 eval（50 条标注）
SKILL_EVAL=1 pytest -m skill_eval tests/test_skill_router.py -q
```

## Wiki + RAG（v4.3.2）

### 数据与权限

- Wiki 文件目录：`backend/data/wiki/`（生产环境请挂载持久卷；已在 `.gitignore`）
- 角色工具白名单需包含 `read_wiki`、`write_wiki`（见 `backend/config/tool_permissions.yaml`）

### 行为

- Agent system prompt 注入 Wiki 索引；用户要求写入 Wiki 时必须调用 **`write_wiki`**
- 上传 `target=auto|wiki|rag` 控制走 Wiki 编译或 RAG 向量库
- 与 **Memory** 分工：偏好/纠正 → memory 或 self-improving；客户/流程知识 → Wiki

详见 [guides/wiki-user.md](./guides/wiki-user.md)。

### 测试

```bash
cd backend
pytest tests/test_wiki_store.py tests/test_wiki_router.py tests/test_wiki_compiler.py \
       tests/test_wiki_write_tool.py tests/test_wiki_smoke_e2e.py -q
```

## 相关文档

- [VERSION.md](./01-项目概览/VERSION.md)
- [wiki-user.md](./guides/wiki-user.md)
- Superpowers 设计：[2026-05-25-skill-routing-plan-gate-design.md](./superpowers/specs/2026-05-25-skill-routing-plan-gate-design.md)
- Wiki 设计：[2026-05-25-llm-wiki-rag-dual-path-design.md](./superpowers/specs/2026-05-25-llm-wiki-rag-dual-path-design.md)
- Skill 编写：[SKILL_AUTHORING.md](./SKILL_AUTHORING.md)

---

*平台文档对齐: TARS v4.3.2 · 见 [VERSION.md](01-项目概览/VERSION.md) · 更新: 2026-05-26*
