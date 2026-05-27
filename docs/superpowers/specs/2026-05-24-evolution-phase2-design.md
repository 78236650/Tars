---
doc_type: spec
status: shipped
platform_version: 4.2.0
catalog: docs/superpowers/README.md
---
# Phase 2：完整自进化系统 — 设计说明

> **文档日期**: 2026-05-24  
> **目标版本**: TARS **v4.2.0** "Data Copilot & Evolution"  
> **状态**: ✅ 已批准（2026-05-24）  
> **对标**: Hermes Agent 自进化（系统级优化，不含 RL/模型训练）

---

## 一、目标与范围

### 1.1 产品目标

**兑现** TARS 自进化对外承诺：从「有 API 无写回」升级为 **可观测、可评估、可回滚** 的完整进化闭环。

进化对象（Phase 2 全部纳入）：

| 对象 | 写回目标 | 驱动信号 |
|------|----------|----------|
| 人格参数 | `workspace/SOUL.md` / tenant soul | A B |
| System / 子代理 Prompt | `workspace/prompts/` 或 AGENTS 片段 | A B |
| 技能描述 | `skills/**/SKILL.md` frontmatter + prompt_template | A B D |
| 子代理委派 | `subagent_manager` 权重 / 关键词映射配置 | A B |
| Insight 场景调优 | insight.yaml 局部阈值（可选，非 SQL） | C |

### 1.2 反馈来源（已确认 A B C D）

- **A** 隐式：工具成败、重复提问、会话长度、提前结束
- **B** 显式：Chat 👍👎、`POST /api/evolution/feedback`
- **C** Insight：MetricAnswerCard 👍👎、adopt/reject
- **D** SkillCurator：`skill_usage` 调用/成功率

**不含 E** Admin 人工标注（Phase 2 不做标注 UI）。

### 1.3 验收标准（已确认 A + B）

**A — 闭环验收**

| # | 项 |
|---|-----|
| A1 | optimize 结果真实写回 workspace / skill 文件 |
| A2 | Agent 主循环每 N 次对话（默认 50）或手动 API 触发 |
| A3 | 每次写回产生 `evolution_audit` 记录，可 diff |
| A4 | `backend/tests/test_evolution*.py` 覆盖率 ≥60%（evolution 包行覆盖） |
| A5 | `EVOLUTION_GUIDE.md` 与实现一致 |

**B — 效果验收**

| # | 项 |
|---|-----|
| B1 | 固定 eval 集 ≥20 场景（对话 + 工具 + 委派 + 技能路由） |
| B2 | 优化前后综合得分提升 **≥10%** |
| B3 | 技能路由：Top-1 命中率或调用成功率提升（A/B 对比） |
| B4 | 子代理委派：任务类型匹配准确率提升（labeled subset） |

### 1.4 Out of Scope

- 模型级 RL / 轨迹导出训练（Hermes 高级能力）
- DSPy/GEPA 完整框架（可用 LLM 辅助改写，不引入新依赖）
- 跨租户全局进化（Phase 2 仅 **tenant-scoped**）
- Admin 标注台

---

## 二、架构方案（选定：方案 2）

### 方案 1：补丁 EvolutionManager（快，脆）

- 给 `_apply_personality_update` 注入 callback
- Agent 末尾调 `record_conversation`
- 缺点：反馈源分散、无统一 eval、skill 优化难扩展

### 方案 2：Evolution 三件套（推荐）

```
FeedbackCollector → EvolutionOrchestrator → ApplyEngine
        ↑                    ↓
   A/B/C/D 信号         EvalRunner (B 验收)
```

- **FeedbackCollector**：统一事件 schema，SQLite `evolution_events`
- **EvolutionOrchestrator**：聚合窗口、触发策略、调用各 Optimizer
- **ApplyEngine**：唯一写回入口，版本化 + audit + rollback
- **EvalRunner**：`tests/evolution/eval_set.yaml` 跑分

### 方案 3：外置 DSPy 服务（过重，不采用）

---

## 三、组件设计

### 3.1 目录结构

```
backend/tars/evolution/
├── manager.py              # 重构：委托 Orchestrator
├── feedback_collector.py   # [新增] 统一入队
├── orchestrator.py         # [新增] 触发与编排
├── apply_engine.py         # [新增] 写回 + audit
├── eval_runner.py          # [新增] eval 集跑分
├── evaluator.py            # 保留，增强隐式信号
├── optimizer.py            # 保留
├── prompt_tuner.py           # 保留
├── skill_optimizer.py        # [新增] 技能描述优化
└── models.py                 # [新增] EvolutionEvent, ApplyRecord
```

### 3.2 FeedbackCollector

**事件类型** `EvolutionEvent`:

```python
@dataclass
class EvolutionEvent:
    tenant_id: str
    user_id: str
    source: str          # implicit | explicit | insight | curator
    signal: str          # tool_fail | thumbs_down | metric_downvote | skill_low_success
    payload: dict        # conversation_id, skill_id, metric_id, ...
    weight: float        # 默认 1.0，explicit/insight 可 2.0
    created_at: datetime
```

**接入点**:

| 来源 | Hook 位置 |
|------|-----------|
| A | `ToolDispatcher` 完成后；`AgentV2` 回合结束 |
| B | Chat WS `message_feedback` 事件；`/api/evolution/feedback` |
| C | `AdoptionService.process_feedback`；Insight 👎 handler |
| D | `SkillCurator.record_call` 扩展 success/fail；定时扫描低成功率 |

存储：`evolution_events` 表 + 保留 `~/.tars/evolution/` 或迁移到 tenant DB。

### 3.3 EvolutionOrchestrator

触发条件（任一）：

1. `conversation_count % optimize_interval == 0`（默认 50）
2. `POST /api/evolution/optimize`
3. Insight 👎 集中窗口（7 天内同 metric ≥3 次）→ 加速触发 skill/prompt 微调

流程：

```
collect_window(days=7) → normalize weights
  → PersonalityOptimizer
  → SubAgentOptimizer (delegation + personality weights)
  → PromptTuner (master + 5 subagents)
  → SkillOptimizer (descriptions for low-success skills)
  → ApplyEngine.apply_all(drafts)  # 需 confidence ≥ threshold
  → EvalRunner.run_baseline_compare()  # 可选 gate：退步则 rollback
```

### 3.4 ApplyEngine（兑现核心）

**唯一写回 API**：

```python
class ApplyEngine:
    def apply_personality(self, tenant_id, params: SoulParameters) -> ApplyRecord
    def apply_prompt(self, tenant_id, prompt_type, content: str) -> ApplyRecord
    def apply_skill_description(self, tenant_id, skill_id, patch: SkillPatch) -> ApplyRecord
    def apply_subagent_config(self, tenant_id, config: SubAgentConfigPatch) -> ApplyRecord
    def rollback(self, apply_id: str) -> None
```

写回规则：

- 人格：更新 tenant workspace `SOUL.md` Parameters 段（via `WorkspaceManager`）
- Prompt：写入 `workspace/prompts/{type}.md`，Agent 构建 system prompt 时读取
- 技能：仅改 SKILL.md `description` + `prompt_template` 非 destructive 段落；**不**改 Python 插件代码
- 子代理：更新 SQLite `subagent_config` 或 yaml snapshot

**Audit** 表 `evolution_apply_log`：

- `id`, `tenant_id`, `target_type`, `target_path`, `before_hash`, `after_hash`, `diff_summary`, `created_at`

### 3.5 SkillOptimizer + Curator 联动

输入：`skill_usage` + 失败率（需在 `record_call` 增 `success: bool`）

逻辑：

- 成功率 < 40% 且 calls ≥ 10 → 生成描述优化建议（LLM 或模板）
- 成功率 < 20% → 建议归档（写入 Curator pending，**不自动归档**，需现有 pending-archive UI 确认）
- Router 命中率：对比 `SkillRouter` 激活 skill vs 用户 👎

### 3.6 Agent 主循环集成

在 `AgentV2` 每轮 assistant 回复完成后：

```python
if evolution_manager.enabled:
    evolution_manager.ingest_turn(
        tenant_id=..., user_id=..., session_id=...,
        query=..., response=..., tools_used=..., subagent=...,
    )
```

`ingest_turn` → FeedbackCollector（隐式）+ 计数 → 可能 trigger orchestrator。

### 3.7 EvalRunner（B 验收）

`backend/tests/evolution/eval_set.yaml`：

- 20+ 场景：分类为 personality_match / tool_choice / skill_route / subagent_delegate
- 每场景：`input`, `expected_tool或skill`, `scoring: rubric`
- CLI：`pytest -m evolution_eval`
- `EvalRunner.compare(before_apply_id, after_apply_id)` → 综合分 + 分项

**Gate 策略**：若 optimize 后 eval 下降 >5%，自动 rollback 最近一次 apply batch。

---

## 四、数据流

```
User turn ends
  → AgentV2.ingest_turn
  → FeedbackCollector.record(implicit)
User 👎 / Insight 👎
  → FeedbackCollector.record(explicit|insight, weight=2.0)
Skill call
  → Curator.record_call(skill_id, success=...)
Cron / threshold
  → Orchestrator.optimize(tenant_id)
  → optimizers produce drafts
  → ApplyEngine.apply_all (if eval gate pass)
  → evolution_apply_log
  → invalidate PromptCache for tenant
Next turn
  → WorkspaceManager loads updated SOUL/prompts/skills
```

---

## 五、错误处理

| 场景 | 行为 |
|------|------|
| 写回文件失败 | 不 commit batch；audit 记 failed |
| eval gate 退步 | rollback batch；log warn |
| 样本不足 (<20 events) | skip optimize，返回 `{skipped: true}` |
| 技能文件只读/ bundled | skip skill apply，仅 log |
| evolution disabled | ingest 仍记录可选（config），不 optimize |

---

## 六、测试计划

| 文件 | 覆盖 |
|------|------|
| `test_evolution_feedback_collector.py` | A/B/C/D 入队 |
| `test_evolution_apply_engine.py` | SOUL 写回、rollback、audit |
| `test_evolution_orchestrator.py` | 触发阈值、batch apply |
| `test_evolution_skill_optimizer.py` | Curator 联动 |
| `test_evolution_agent_integration.py` | ingest_turn 挂钩 |
| `test_evolution_eval_runner.py` | eval_set 跑分 |
| `evolution/eval_set.yaml` | ≥20 场景 |

---

## 七、实施顺序（约 12–15 人日）

| W | 工作包 |
|---|--------|
| W1 | FeedbackCollector + DB schema + hooks (A) |
| W2 | ApplyEngine + personality/prompt 写回 (A1,A3) |
| W3 | Agent ingest_turn + auto trigger (A2) |
| W4 | Explicit + Insight hooks (B,C) |
| W5 | SkillOptimizer + Curator success bit (D) |
| W6 | SubAgentOptimizer 写回 |
| W7 | EvalRunner + eval_set.yaml (B1-B4) |
| W8 | Tests ≥60% + EVOLUTION_GUIDE 更新 |

---

## 八、风险

| 风险 | 缓解 |
|------|------|
| 错误写回污染 workspace | eval gate + rollback + dry-run API |
| LLM 改 prompt 漂移 | 限制 diff 幅度；仅 append tuning 段 |
| 多 tenant 隔离 | 所有 apply tenant-scoped |
| Phase 1 未完成的 Insight 反馈 | C 源可 stub，W4 依赖 Phase 1 MetricAnswerCard |

---

*评审通过后写入 implementation plan，并进入 Phase 3（对标 OpenClaw）头脑风暴。*
