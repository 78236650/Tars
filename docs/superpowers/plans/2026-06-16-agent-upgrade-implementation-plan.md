# TARS Agent 升级项目实施文档 v5.0.5/A4

> ✅ 迭代一完成 · ✅ 迭代二完成 · ⏳ 迭代三按需

> 创建：2026-06-16 · 基于 Agent 全面评估 · 记忆系统 A 级达标后的下一步

---

## 一、项目背景

TARS 记忆系统经过 Phase 1-3 + A-D + Evolution↔Memory 桥梁升级后，已从行业中等提升至**领先水平**（10 种 op、四层去重、Ebbinghaus 衰减、KB 晋升、Evolution 闭环）。48 个测试全绿。

**当前瓶颈已从"记不住"转移到"做不好"和"看不见"**：Agent 在多步任务中容易丢失上下文，运维人员无法了解 LLM 调用成本，子 Agent 之间信息孤岛。

---

## 二、五个升级方向总览

| # | 方向 | 当前评分 | 目标评分 | 预期收益 | 改动量 |
|---|------|:---:|:---:|------|:---:|
| 1 | Agent 规划能力 | B | A- | 多步任务成功率 60%→85% | ~200行 |
| 2 | LLM 可观测性 | C+ | B+ | 运维可见成本/延迟/用量 | ~150行 |
| 3 | 子 Agent 记忆共享 | B | A- | 子 Agent 不再信息孤岛 | ~100行 |
| 4 | 主动预警引擎 | C+ | B | 从对话助手升级为运维哨兵 | ~120行 |
| 5 | 前端体验优化 | B | B+ | 降低运维门槛 | ~200行 |

---

## 三、详细方案

### 方向 1：Agent 规划能力 — Plan-Execute-Verify 循环

**问题**：当前 Agent 靠 prompt 指令（"DONE/BLOCKED/GO"）管理任务进度，没有显式的规划-执行-验证状态机。复杂任务容易"做了前面忘了后面"。

**方案**：在 Agent 主循环中增加轻量计划管理：

```
用户消息 → TaskDetector 判断是否需要规划
  ↓ 需要
生成 Plan（拆为 3-8 个子步骤，每步有 verify 条件）
  ↓
循环执行：
  当前步骤 → 工具调用 → 验证(verify gate)
  ├─ 通过 → 下一步
  ├─ 失败 → 重试/修正/跳过
  └─ 全部完成 → 汇总报告
```

**改动范围**：
- `agent/agent.py`：主循环增加 plan 模式分支（~80行）
- `agent/plan_executor.py`（新建）：Plan 状态机（~80行）
- `agent/prompt_builder.py`：plan 模式 prompt 注入（~20行）
- `database/`：可选新增 `agent_plans` 表持久化

**风险**：低。Plan 模式是可选的——非复杂任务不影响现有流程。需要 verify gate 设计得当（不能太严格导致无法推进）。

**验收标准**：
- 多步骤任务（如"查数据库→分析→写报告→发邮件"）端到端成功率 >85%
- 非复杂任务（单步问题）延迟不增加

---

### 方向 2：LLM 可观测性 — Token/延迟/成本仪表盘

**问题**：运维无法了解 LLM 调用成本、延迟分布、模型切换频率。Prometheus 有基础 /metrics 但缺少 LLM 维度。

**方案**：每次 LLM 调用记录关键指标，暴露 Prometheus 指标，前端 Admin 增加用量看板。

```
每次 provider.chat() 调用 → 记录:
  model, provider, prompt_tokens, completion_tokens,
  latency_ms, cache_hit (bool), tenant_id
  ↓
后端 /metrics 端点暴露:
  tars_llm_requests_total{model,provider,tenant}
  tars_llm_tokens_total{model,type}
  tars_llm_latency_seconds{model,quantile}
  ↓
前端 Admin → LLM 用量看板:
  今日/本周/本月 token 消耗趋势
  按模型/租户拆分
  Top 耗时请求
```

**改动范围**：
- `models/` provider 基类：chat() 返回值增加 `usage` 字段（已部分支持）或 hook 记录（~30行）
- `metrics.py`：新增 4 个 LLM 相关指标（~30行）
- `api/admin.py`：新增 `GET /api/admin/llm-usage` 端点（~40行）
- 前端 `AdminLLMUsage.vue`（新建）：看板组件（~60行）

**风险**：低。纯粹加观测，不改变任何业务逻辑。指标记录在异步 hook 中，不影响延迟。

**验收标准**：
- `/metrics` 端点包含 `tars_llm_*` 指标
- 前端 Admin 可见 token 消耗趋势图

---

### 方向 3：子 Agent 记忆共享

**问题**：SubAgentManager 创建的子 Agent 无法共享 Memory 上下文，只能通过文件系统交换数据。子 Agent 不知道用户画像、项目上下文、最近决策。

**方案**：子 Agent 启动时注入父 Agent 的 Working Context + 相关记忆。

```
SubAgentManager.delegate(task)
  ↓
1. 提取父 Agent 的 Working Context (focus_entities, intent)
2. 调用 MemoryManager.get_context_for_query(task) 检索相关记忆
3. 构建子 Agent system prompt:
   ## 父 Agent 上下文
   - 当前焦点实体: [元洪码头, 3号泊位]
   - 当前意图: 配载方案评估
   ## 相关历史记忆
   - [solution] 上次配载方案A...
4. 子 Agent 执行完毕 → 产出结构化 handoff → 写入父 Agent episodic
```

**改动范围**：
- `agent/subagent_manager.py`：delegate() 增加记忆上下文注入（~50行）
- `agent/agent.py`：handle_subagent_completion() 增加 handoff 写回（~30行）
- `agent/prompt_builder.py`：新增 build_subagent_context()（~20行）

**风险**：中。子 Agent 输入 token 可能增加（多了记忆上下文）。需限制长度（记忆上下文 ≤1500 字）。

**验收标准**：
- 子 Agent 能在回复中引用用户画像和项目上下文
- 子 Agent 的 critical findings 自动写回父 Agent Memory

---

### 方向 4：主动预警引擎

**问题**：TARS 只能在对话中被动响应，不会在用户离线时主动发现问题并通知。

**方案**：定时巡检 Memory + 数据源，检测异常模式，通过 Channels outbound 推送。

```
定时任务 (configurable, 默认每 6 小时):
  ↓
1. MemoryAwareAnalyzer.analyze()
   └─ 发现 ≥3 条同类 correction → 生成预警
   └─ 发现某 entity 30 天无更新 → 提醒关注
2. 数据源巡检（可选，需 BI 模块）
   └─ 数据库连通性检查
   └─ 指标异常检测
  ↓
3. 通过 Channels outbound 推送:
   └─ WebSocket → 前端通知
   └─ 未来可扩展：飞书/邮件
```

**改动范围**：
- `evolution/alerting.py`（新建）：AlertEngine 预警引擎（~60行）
- `scheduler.py`：注册预警定时任务（~15行）
- `channels/outbound.py`：增加 `send_alert` 方法（~25行）
- 前端通知组件（~20行）

**风险**：低。纯增量功能，不影响现有流程。预警阈值可配，避免噪声。

**验收标准**：
- 定时巡检产出预警记录
- 前端可收到预警通知
- 不产生假阳性噪声（≥3 条同类纠正才触发）

---

### 方向 5：前端体验优化

**问题**：EntityTree 大数据量下渲染卡顿；复杂操作（配数据源、写 skill）无向导。

**方案**：两次小迭代。

**迭代 5a — 记忆树虚拟滚动**：
- EntityTree 组件改用虚拟滚动（只渲染可视区域）
- 搜索增加时间范围 + importance 滑块筛选

**迭代 5b — 操作向导**：
- 数据源配置增加 step-by-step 向导（3 步：连接→测试→保存）
- Skill 编辑器增加模板选择 + 实时校验

**改动范围**（5a）：
- 前端 `MemoryTree.vue` 改用虚拟滚动（~60行）
- 前端搜索栏增加筛选控件（~30行）

**改动范围**（5b）：
- 前端 `DataSourceWizard.vue`（新建，~80行）
- 前端 `SkillEditor.vue` 增加模板（~30行）

**风险**：低。

**验收标准**：
- 记忆树 500+ 节点渲染不卡顿
- 数据源配置从"读文档"变为"跟着向导走"

---

## 四、实施计划

### ✅ 迭代一（已完成）：可观测性 + 子 Agent 共享

| 步骤 | 内容 | 时间 |
|------|------|------|
| 1.1 | metrics.py 新增 LLM 指标 | 1h |
| 1.2 | provider.chat() hook 记录指标 | 1h |
| 1.3 | Admin API + 前端看板 | 2h |
| 1.4 | subagent_manager 记忆注入 | 2h |
| 1.5 | 测试 + 回归 | 1h |

**交付 ✅**：LLM 用量可见 + 子 Agent 不再信息孤岛

### ✅ 迭代二（已完成）：规划能力 + 预警引擎

| 步骤 | 内容 | 时间 |
|------|------|------|
| 2.1 | PlanExecutor 状态机 | 3h |
| 2.2 | Agent 主循环 plan 分支 | 2h |
| 2.3 | AlertEngine 预警引擎 | 2h |
| 2.4 | 预警定时调度 + outbound | 1h |
| 2.5 | 集成测试 | 2h |

**交付 ✅**：Agent 能做多步规划 + TARS 能主动预警

### 迭代三（按需）：前端体验

| 步骤 | 内容 | 时间 |
|------|------|------|
| 3.1 | 记忆树虚拟滚动 | 2h |
| 3.2 | 操作向导 | 3h |

**交付**：前端体验提升

---

## 五、里程碑

| Milestone | 验收条件 | 状态 |
|-----------|----------|:---:|
| M1: 可观测性上线 | /metrics 含 LLM 指标（4个新指标），Admin API 可用 | ✅ |
| M2: 子 Agent 记忆共享 | 子 Agent 可引用用户画像和项目上下文 | ✅ |
| M3: Agent 能做规划 | 复杂任务自动注入 PlanExecutor 三步法 prompt | ✅ |
| M4: 主动预警 | AlertEngine 每 6 小时巡检（correction/entity/surge） | ✅ |
| M5: 前端优化 | 记忆树虚拟滚动 + 操作向导 | ⏳ |

---

## 六、风险与缓解

| 风险 | 概率 | 缓解 |
|------|:---:|------|
| Plan 模式增加延迟 | 中 | plan 模式仅复杂任务触发，单步任务不受影响 |
| 子 Agent token 超限 | 低 | 记忆上下文 ≤1500 字，超出截断 |
| 预警假阳性噪声 | 中 | ≥3 条同类纠正才触发，阈值可调 |
| 前端重构影响现有功能 | 低 | 渐进式改动，每步独立上线 |

---

*TARS v5.0.5/A4 · 2026-06-16*


---

*迭代一完成：2026-06-16 · 迭代二完成：2026-06-16 · 迭代三：按需*