---
doc_type: plan
status: shipped
platform_version: 4.3.2
catalog: docs/superpowers/README.md
---
# Skill 路由 + Plan 门控 + Verification Gate — 实施计划

> **Goal:** 借鉴 Superpowers 框架，为 TARS 增加 Skill 自动路由、Plan 审批门控、完成前验证三项能力。
>
> **Spec:** [2026-05-25-skill-routing-plan-gate-design.md](../specs/2026-05-25-skill-routing-plan-gate-design.md)
>
> **Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / asyncio / React + TypeScript
>
> **预计工期:** 4 个里程碑，每个 1–2 天

---

## 里程碑总览

| 里程碑 | 交付物 | 依赖 | 验收 |
|--------|--------|------|------|
| **M1** | Skill 自动路由 | 无 | eval 命中率 ≥ 80% |
| **M2** | Plan 审批门控 | M1（可选） | 断点恢复 + 前端审批 |
| **M3** | Verification Gate | M2 | verify 失败阻断 |
| **M4** | 联调 + 文档 | M1+M2+M3 | 全链路 demo |

M1/M2/M3 之间无硬依赖，可并行开发；M4 需要三者都完成。

---

## M1 — Skill 自动路由

### Task 1.1: Skill 模型扩展

**Files:**
- Modify: `backend/tars/skills/models.py`（如无此文件则在 `registry.py` 中）

- [ ] Step 1: `Skill` dataclass 增加 `triggers: List[str]`、`skip_when: List[str]`、`priority: int = 50`
- [ ] Step 2: 所有字段 optional，缺失时不参与路由

### Task 1.2: Skill Loader 解析新字段

**Files:**
- Modify: `backend/tars/skills/loader.py`

- [ ] Step 1: YAML frontmatter 解析增加 triggers / skip_when / priority
- [ ] Step 2: 向后兼容：旧 YAML 无新字段时默认空列表

### Task 1.3: IntentExtractor

**Files:**
- Create: `backend/tars/skills/intent_extractor.py`

- [ ] Step 1: `extract(message: str) -> Intent` — 返回关键词 + embedding vector
- [ ] Step 2: 复用现有 `bge-small-zh-v1.5` embedding（从 `memory/embeddings.py` 引入）
- [ ] Step 3: 关键词提取：jieba 分词 + 停用词过滤（已有依赖）

### Task 1.4: SkillRouter

**Files:**
- Create: `backend/tars/skills/router.py`

- [ ] Step 1: `SkillRouter.__init__(registry, embeddings, config)`
- [ ] Step 2: `match(intent, context) -> List[SkillCandidate]`
  - 阶段 1：正则匹配 triggers（快速过滤）
  - 阶段 2：embedding 余弦相似度排序
  - 阶段 3：skip_when 过滤
  - 阶段 4：按 priority + score 排序，返回 top_k
- [ ] Step 3: `SkillCandidate` dataclass: `skill_id, score, match_reason`
- [ ] Step 4: 缓存 skill embedding（启动时预计算）

### Task 1.5: Agent 主循环集成

**Files:**
- Modify: `backend/tars/agent/agent.py`

- [ ] Step 1: 在 tool dispatch 前调用 `router.match()`
- [ ] Step 2: 将候选 skill 注入 system prompt 或 tool 列表（让 LLM 感知推荐）
- [ ] Step 3: Agent 保留最终决策权 — 候选仅作为提示

### Task 1.6: 路由配置

**Files:**
- Modify: `backend/tars/config/skills.py`
- Modify: `backend/config/modules.yaml`

- [ ] Step 1: 新增 `SkillRoutingConfig`: enabled, top_k, min_score, use_embedding, cache_ttl_sec
- [ ] Step 2: `modules.yaml` 增加 `skill_routing` 段

### Task 1.7: Eval 测试集

**Files:**
- Create: `backend/tests/test_skill_router.py`
- Create: `backend/tests/fixtures/skill_routing_eval.yaml`

- [ ] Step 1: 编写 50 条 `{intent, expected_skill, context}` 标注
- [ ] Step 2: 单测：正则匹配、embedding 匹配、skip_when 过滤
- [ ] Step 3: Eval runner：命中率 / 误触发率断言

### Task 1.8: 为现有高频 Skill 补充 triggers

**Files:**
- Modify: 各 skill YAML（bi_query, knowledge_search, insight_*, memory 等）

- [ ] Step 1: 为 top-10 高频 skill 补充 triggers + skip_when
- [ ] Step 2: 确保 eval 通过

---

## M2 — Plan 审批门控

### Task 2.1: TaskPlan 模型升级

**Files:**
- Modify: `backend/tars/orchestration/models.py`

- [ ] Step 1: `TaskPlan` 增加 `status` 字段（draft/approved/executing/done/failed/rejected/cancelled）
- [ ] Step 2: 增加 `PlanCheckpoint` dataclass
- [ ] Step 3: 增加 `auto_approve_eligible(plan) -> bool` 判定逻辑

### Task 2.2: Plan Store

**Files:**
- Create: `backend/tars/database/plan_store.py`

- [ ] Step 1: `PlanStore`: create / update_status / add_checkpoint / get / list_by_tenant
- [ ] Step 2: SQLite 表：`task_plans` + `plan_checkpoints`
- [ ] Step 3: 单测

### Task 2.3: PlanExecutor

**Files:**
- Create: `backend/tars/orchestration/executor.py`

- [ ] Step 1: `PlanExecutor.execute(plan)` — 逐步执行 + 写 checkpoint
- [ ] Step 2: 每步执行前检查 `plan.status == approved/executing`（用户可能中途取消）
- [ ] Step 3: 步骤失败 → 标 failed + 记录失败 step_id
- [ ] Step 4: `resume(plan_id)` — 从最后成功 checkpoint 之后继续
- [ ] Step 5: 危险工具检测：`DANGEROUS_TOOLS = {"shell", "file_write", "network"}`

### Task 2.4: Planner 改造

**Files:**
- Modify: `backend/tars/orchestration/planner.py`

- [ ] Step 1: 生成计划后设 `status=draft`，不自动执行
- [ ] Step 2: 判断 `auto_approve_eligible` → 是则直接设 approved + 执行
- [ ] Step 3: 否则推送 WebSocket 等待用户

### Task 2.5: WebSocket 推送

**Files:**
- Modify: `backend/tars/channels/websocket.py`

- [ ] Step 1: 新增 event type: `plan_review_request`
- [ ] Step 2: payload: `{plan_id, goal, steps[], estimated_duration_sec}`
- [ ] Step 3: 5 分钟时推送 `plan_review_reminder` 提醒
- [ ] Step 4: 超时 10 分钟无响应 → 自动 cancel

### Task 2.6: Plan API

**Files:**
- Create: `backend/tars/api/plans.py`
- Modify: `backend/tars/main.py`（注册路由）

- [ ] Step 1: `POST /api/plans/{id}/approve` — 批准（可带修改后的 steps）
- [ ] Step 2: `POST /api/plans/{id}/reject` — 拒绝
- [ ] Step 3: `POST /api/plans/{id}/retry` — 从断点恢复
- [ ] Step 4: `GET /api/plans` — 列表
- [ ] Step 5: `GET /api/plans/{id}` — 详情含 checkpoints

### Task 2.7: 前端 PlanReviewDialog

**Files:**
- Create: `frontend/src/components/PlanReviewDialog.tsx`
- Modify: `frontend/src/hooks/useWebSocket.ts`（监听新 event）

- [ ] Step 1: Dialog 展示步骤列表 + 工具标签 + 预估耗时
- [ ] Step 2: 批准 / 拒绝按钮
- [ ] Step 3: 步骤可删除（简单编辑）
- [ ] Step 4: 执行中展示进度（哪步在跑、哪步完成）

### Task 2.8: 集成测试

**Files:**
- Create: `backend/tests/test_plan_gate_e2e.py`

- [ ] Step 1: 测试完整生命周期：draft → approve → execute → done
- [ ] Step 2: 测试断点恢复：step 2 失败 → retry → 从 step 2 继续
- [ ] Step 3: 测试 auto_approve 路径
- [ ] Step 4: 测试超时 cancel

---

## M3 — Verification Gate

### Task 3.1: Skill 模型加 verify 字段

**Files:**
- Modify: `backend/tars/skills/models.py`

- [ ] Step 1: `Skill` 增加 `verify: List[VerifyStep]`
- [ ] Step 2: `VerifyStep`: command, expect, timeout_sec
- [ ] Step 3: `Skill` 增加 `verify_mode: str = "strict"`（strict / lenient）

### Task 3.2: Expect 条件解析器

**Files:**
- Create: `backend/tars/orchestration/verification.py`

- [ ] Step 1: 解析 expect 语法：`exit_code == 0`, `stdout contains "X"`, `duration_ms < N`
- [ ] Step 2: `VerificationGate.run(verify_steps, mode) -> VerifyResult`
- [ ] Step 3: 逐条执行 command（subprocess），检查 expect
- [ ] Step 4: `strict` 模式：全部通过 → pass；任一失败 → fail
- [ ] Step 5: `lenient` 模式：通过率 ≥ 80% → `done_with_warnings`；< 80% → fail

### Task 3.3: Executor 集成

**Files:**
- Modify: `backend/tars/orchestration/executor.py`

- [ ] Step 1: Plan 执行完最后一步后，检查关联 skill 是否有 verify
- [ ] Step 2: 有 → 调 `VerificationGate.run()`
- [ ] Step 3: 通过 → done；失败 → failed + 写 audit

### Task 3.4: Audit 记录

**Files:**
- Modify: `backend/tars/database/audit_store.py`（或新建）

- [ ] Step 1: `verification_audit` 表：plan_id, step_results[], passed, timestamp
- [ ] Step 2: API 可查询验证历史

### Task 3.5: 单元测试

**Files:**
- Create: `backend/tests/test_verification_gate.py`

- [ ] Step 1: expect 解析器各条件测试
- [ ] Step 2: 命令执行 + 超时测试
- [ ] Step 3: 全通过 / 部分失败 / 全失败场景

---

## M4 — 联调 + 文档

### Task 4.1: 全链路 E2E

- [ ] Step 1: 场景：用户说"帮我部署服务" → Router 匹配 deploy skill → 生成 5 步 plan → 用户审批 → 执行 → verify 通过 → done
- [ ] Step 2: 场景：verify 失败 → 用户看到失败原因 → retry
- [ ] Step 3: 场景：简单任务（2 步）→ auto_approve → 直接执行

### Task 4.2: 文档

- [ ] Step 1: `docs/UPGRADE_GUIDE_v4.3.2.md` — 升级说明
- [ ] Step 2: `docs/SKILL_AUTHORING.md` — 如何编写带 triggers/verify 的 skill
- [ ] Step 3: 更新 README 相关章节

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|------|------|------|
| Router 误匹配 | Agent 保留决策权；eval 门控 | `skill_routing.enabled: false` |
| Plan 审批阻断体验 | auto_approve 简单任务 | `plan_gate.enabled: false` |
| Verify 命令有副作用 | 文档约束只读命令 | `verification.enabled: false` |
| 前端未升级 | 后端 fallback auto_approve | — |

---

## 开发顺序建议

```
Week 1:  M1（Skill 路由）— 后端为主，无前端依赖
Week 1:  M3（Verification）— 可与 M1 并行，独立模块
Week 2:  M2（Plan 门控）— 含前端，工作量最大
Week 2:  M4（联调）— M1+M2+M3 完成后
```

M1 和 M3 无依赖关系，可以并行开发。M2 依赖 M1 的 Skill 模型变更（共享 `models.py`），但核心逻辑独立。
