# Skill 自动路由 + Plan 审批门控 + 验证门控 — 设计说明

> **文档日期**: 2026-05-25
> **目标版本**: TARS **v4.3.2**（v4.3.x patch；原稿 v4.4.0）
> **状态**: Draft — 待评审
> **借鉴**: [obra/superpowers](https://github.com/anthropics/claude-code) skill 触发元数据、plan-execute 分离、verification gate

---

## 一、目标与范围

### 1.1 产品目标

借鉴 Superpowers 框架三个核心模式，升级 TARS 的技能调度、任务规划和质量门控能力：

| # | 升级方向 | 一句话 |
|---|----------|--------|
| **U1** | Skill 触发元数据 + 自动路由 | Agent 收到请求时自动匹配最佳 skill，无需用户显式调用 |
| **U2** | Plan 审批门控 | 复杂任务先生成计划 → 用户审批 → 分步执行带 checkpoint |
| **U3** | Verification Gate | 任务声称完成前强制跑验证命令，通过才标 done |

### 1.2 现状问题

| 模块 | 现状 | 问题 |
|------|------|------|
| `skills/registry.py` | LLM 自由选择或用户显式调用 | 低频 skill 被遗忘；高频 skill 被误触发；无 skip 条件 |
| `orchestration/planner.py` | 一次性生成 + 自动执行 | 用户无法审批/修正计划；失败无法断点恢复 |
| `evolution/eval_runner.py` | 事后评估 | 不阻断错误输出；用户已看到错误结果后才发现问题 |

### 1.3 验收标准

**U1 — Skill 自动路由**

| # | 项 |
|---|-----|
| A1 | Skill YAML 支持 `triggers` / `skip_when` 字段 |
| A2 | `SkillRouter.match(intent)` 返回 top-K 候选（K=3），耗时 < 50ms |
| A3 | Agent 主循环在 tool dispatch 前自动过 skill match |
| A4 | 命中率 ≥ 80%（基于 50 条标注 intent 的 eval） |
| A5 | 误触发率 ≤ 5%（skip_when 生效） |

**U2 — Plan 审批门控**

| # | 项 |
|---|-----|
| B1 | `TaskPlan.status` 支持 `draft → approved → executing → done / failed` |
| B2 | 生成计划后 WebSocket 推送给前端，暂停等待用户确认 |
| B3 | 执行时每步写 checkpoint；失败可从断点恢复 |
| B4 | 前端 PlanReviewDialog 可展示/编辑/批准/拒绝计划 |
| B5 | `force_auto_approve` 配置项可跳过审批（简单任务或 CI 场景） |

**U3 — Verification Gate**

| # | 项 |
|---|-----|
| C1 | Skill/Pipeline YAML 支持 `verify` 字段（命令列表 + 期望条件） |
| C2 | Pipeline 最后一步完成后自动跑 verify |
| C3 | 验证失败 → 状态回退 + 通知用户，不标 done |
| C4 | 验证结果写入 `execution_audit` |

### 1.4 明确不做（Non-goals）

- 不做 skill 自动生成（保留在 Evolution Phase 3）
- 不做分布式 plan 执行（仍单 worker）
- 不做前端 plan 编辑器的拖拽排序（仅文本编辑）
- 不改 LLM 模型选择逻辑

---

## 二、U1 — Skill 触发元数据 + 自动路由

### 2.1 Skill YAML 扩展

```yaml
# skills/bi_query/SKILL.md (frontmatter)
name: bi_query
description: 执行 BI 数据查询并生成图表
type: tool_skill
triggers:
  - "查询数据"
  - "生成报表"
  - "看一下.*指标"
  - intent:bi_query          # 语义 intent 标签
skip_when:
  - "解释.*代码"
  - intent:general_chat
  - context:no_datasource    # 上下文条件：无数据源时跳过
priority: 80                 # 0-100，冲突时高优先级胜出
```

### 2.2 SkillRouter 架构

```
用户消息 → IntentExtractor（轻量 embedding / 关键词）
         → SkillRouter.match(intent, context)
              ├─ 关键词匹配（triggers 正则）
              ├─ 语义匹配（intent embedding vs skill embedding）
              └─ 上下文过滤（skip_when 条件）
         → Top-K 候选 → Agent 决策（LLM 从候选中选或不选）
```

**关键设计决策：**

- **两阶段匹配**：先快速正则/关键词过滤（< 5ms），再语义排序（< 45ms）
- **Agent 保留最终决策权**：Router 只提供候选，不强制执行
- **Context 条件**：`skip_when` 支持 `context:xxx` 前缀，检查运行时状态（如是否有数据源、是否在会议中）

### 2.3 新增/修改文件

| 文件 | 操作 | 职责 |
|------|------|------|
| `tars/skills/router.py` | Create | SkillRouter：match / rank / filter |
| `tars/skills/intent_extractor.py` | Create | 轻量 intent 提取（复用 bge-small-zh-v1.5） |
| `tars/skills/models.py` | Modify | Skill 模型加 triggers/skip_when/priority |
| `tars/skills/loader.py` | Modify | 解析新 frontmatter 字段 |
| `tars/agent/agent.py` | Modify | 主循环集成 SkillRouter |
| `tars/config/skills.py` | Modify | 路由配置（top_k, threshold） |

### 2.4 配置

```yaml
# config/skills.yaml 新增
routing:
  enabled: true
  top_k: 3
  min_score: 0.3            # 低于此分不推荐
  use_embedding: true       # false 则仅用正则
  embedding_model: bge-small-zh-v1.5
  cache_ttl_sec: 300
```

---

## 三、U2 — Plan 审批门控

### 3.1 TaskPlan 状态机

```
draft ──[用户批准]──→ approved ──[开始执行]──→ executing ──[全部完成]──→ done
  │                      │                        │
  │ [用户拒绝/超时]       │ [用户取消]              │ [步骤失败]
  ↓                      ↓                        ↓
rejected              cancelled                 failed
                                                  │
                                              [用户重试]
                                                  ↓
                                              executing (从 checkpoint 恢复)
```

### 3.2 Checkpoint 机制

```python
@dataclass
class PlanCheckpoint:
    plan_id: str
    step_id: int
    status: str              # "done" | "failed" | "skipped"
    output: Optional[str]    # 步骤输出摘要
    timestamp: str
    retry_count: int = 0
```

每步执行完写入 `plan_checkpoints` 表。恢复时从最后一个 `status=done` 的 step 之后继续。

### 3.3 触发条件（何时走审批 vs 直接执行）

| 条件 | 行为 |
|------|------|
| steps ≥ 3 且含危险工具（shell/file_write/network） | 必须审批 |
| steps ≥ 5（任意工具） | 必须审批 |
| steps < 3 且仅安全工具 | 自动执行（`force_auto_approve`） |
| 用户设置 `always_approve_plans: true` | 全部审批 |

### 3.4 前端交互

- WebSocket event: `plan_review_request`（含完整 plan JSON）
- 前端展示 `PlanReviewDialog`：步骤列表 + 预估耗时 + 批准/拒绝/编辑
- 用户可删除/重排步骤后批准
- 5 分钟时推送提醒通知（`plan_review_reminder`）
- 超时 10 分钟无响应 → 自动取消 + 通知

### 3.5 新增/修改文件

| 文件 | 操作 | 职责 |
|------|------|------|
| `tars/orchestration/models.py` | Modify | TaskPlan 加 status/checkpoints |
| `tars/orchestration/executor.py` | Create | PlanExecutor：分步执行 + checkpoint |
| `tars/orchestration/planner.py` | Modify | 生成后设 status=draft，不自动执行 |
| `tars/database/plan_store.py` | Create | plan + checkpoint 持久化 |
| `tars/channels/websocket.py` | Modify | 推送 plan_review_request |
| `tars/api/plans.py` | Create | REST: approve/reject/retry/list |
| `frontend/src/components/PlanReviewDialog.tsx` | Create | 审批 UI |

---

## 四、U3 — Verification Gate

### 4.1 Skill/Pipeline 验证声明

```yaml
# skills/deploy/SKILL.md
name: deploy
verify:
  - command: "curl -sf http://localhost:8000/health"
    expect: status_code == 200
    timeout_sec: 10
  - command: "pytest tests/smoke/ -x -q"
    expect: exit_code == 0
    timeout_sec: 60
```

### 4.2 验证执行流程

```
Pipeline 最后一步完成
  → VerificationGate.run(skill.verify)
      ├─ 逐条执行 command
      ├─ 检查 expect 条件
      └─ 全部通过 → status=done
         任一失败 → status=failed + 回退 + 通知
  → 写入 execution_audit
```

### 4.3 expect 条件语法

| 条件 | 含义 |
|------|------|
| `exit_code == 0` | 命令退出码为 0 |
| `status_code == 200` | HTTP 状态码 |
| `stdout contains "OK"` | 输出包含字符串 |
| `stdout not contains "ERROR"` | 输出不包含 |
| `duration_ms < 5000` | 执行时间限制 |

### 4.4 验证模式

| 模式 | 行为 |
|------|------|
| `strict`（默认） | 全部 verify step 通过才标 done；任一失败 → fail |
| `lenient` | 通过率 ≥ 80% → `done_with_warnings`；< 80% → fail |

per-skill 配置：

```yaml
# skills/deploy/SKILL.md
verify_mode: strict    # 或 lenient
verify:
  - command: "curl -sf http://localhost:8000/health"
    expect: exit_code == 0
```

### 4.4 新增/修改文件

| 文件 | 操作 | 职责 |
|------|------|------|
| `tars/orchestration/verification.py` | Create | VerificationGate：执行 + 判定 |
| `tars/orchestration/executor.py` | Modify | 执行完调 verification |
| `tars/skills/models.py` | Modify | Skill 模型加 verify 字段 |
| `tars/database/audit_store.py` | Modify | 写入验证结果 |

---

## 五、配置变更汇总

```yaml
# config/modules.yaml 新增
skill_routing:
  enabled: true

plan_gate:
  enabled: true
  always_approve: false
  auto_approve_threshold: 3    # steps < 此值且无危险工具时自动批准
  review_timeout_sec: 600      # 10 分钟
  reminder_at_sec: 300         # 5 分钟时推提醒

verification:
  enabled: true
  default_mode: strict         # strict | lenient
  lenient_pass_rate: 0.8       # lenient 模式下通过率阈值
  fail_action: "rollback"      # rollback | warn_only
```

---

## 六、兼容性与风险

| 风险 | 缓解 |
|------|------|
| Skill 路由误匹配导致错误执行 | Router 仅推荐，Agent 保留最终决策；skip_when 兜底 |
| Plan 审批阻断用户体验 | auto_approve 对简单任务跳过；超时自动取消 |
| Verification 命令本身有副作用 | verify 命令应为只读；文档约束 + sandbox |
| 旧 skill YAML 无新字段 | 全部字段 optional，缺失时走原有逻辑 |
| 前端未升级时 plan 审批不可用 | 后端 fallback：无 WS 连接时 auto_approve |

**回滚：** 三个功能均有独立 `enabled` 开关，关闭即恢复原有行为。

---

## 七、测试策略

| 层级 | 范围 | 运行方式 |
|------|------|----------|
| L1 单元 | SkillRouter match/rank、PlanExecutor checkpoint、VerificationGate expect 解析 | `pytest tests/test_skill_router.py tests/test_plan_executor.py tests/test_verification_gate.py` |
| L2 集成 | Agent 主循环 + Router 联动、Plan 全生命周期、Verify 失败回退 | `pytest tests/test_skill_routing_e2e.py tests/test_plan_gate_e2e.py` |
| L3 Eval | 50 条标注 intent 命中率 | `SKILL_EVAL=1 pytest -m skill_eval` |

---

## 八、里程碑

| 里程碑 | 交付 | 验收 |
|--------|------|------|
| **M1 — Skill 路由** | SkillRouter + intent_extractor + Agent 集成 + eval | 命中率 ≥ 80%；误触发 ≤ 5% |
| **M2 — Plan 门控** | PlanExecutor + checkpoint + API + 前端 Dialog | 3+ 步任务走审批；断点恢复可用 |
| **M3 — Verification Gate** | VerificationGate + expect 解析 + audit | verify 失败阻断 done；审计可查 |
| **M4 — 联调 + 文档** | 三者联动 e2e + UPGRADE_GUIDE.md | 全链路 demo 通过 |

---

## 九、开放问题

1. ~~**Skill 路由的 embedding 模型**~~ → **已决策：复用现有 `bge-small-zh-v1.5`**，不引入新模型
2. ~~**Plan 审批超时**~~ → **已决策：默认 10 分钟**；5 分钟时推一次提醒通知；超时后自动 cancel
3. ~~**Verification Gate 部分通过**~~ → **已决策：支持两种模式**
   - `strict`（默认）：全部通过才标 done
   - `lenient`：通过率 ≥ 80% 则标 `done_with_warnings`，低于 80% 标 fail
   - per-skill 可配 `verify_mode: strict | lenient`
4. **U1 和现有 Evolution SkillOptimizer 的关系**：路由命中率数据是否反哺 optimizer？— 建议 M4 联调时接入
5. **Plan checkpoint 存储**：SQLite 还是独立文件？— 建议 SQLite（与现有 store 一致），定期清理 > 30 天的记录
