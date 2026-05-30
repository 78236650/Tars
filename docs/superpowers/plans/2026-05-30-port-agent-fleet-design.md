---
doc_type: plan
status: shipped
platform_version: v4.4.0
---

# 港航物流 Agent 集群 · 完整项目规划与架构设计

> **本文件交付物：** 完整项目规划 · 架构设计 · 模块拆分 · 目录结构 · 开发规范 · 任务排期
> **配套文件：** 记忆与调度融合设计 `2026-05-30-portlogistics-agent-memory-design.md`（本文件依赖它的共享记忆层）
> **日期：** 2026-05-30 　**版本目标：** v4.4.0 → v4.5.0 「港航 Agent 集群」
> **给执行团队（牛马）：** 本文是蓝图。每个 Agent 都套用现有 `SubAgent` 抽象基类（已核对 `backend/tars/agent/subagents/base.py`），不另起炉灶。照 Phase 顺序做，每个 Task 独立可跑、可测、可提交。

---

## 一、项目目标与边界

### 1.1 一句话目标
把 TARS 从「5 个通用子 Agent」扩展为「**总调度 Agent + N 个港航环节专家 Agent**」的集群，每个环节 Agent 懂自己的领域、读得到领域记忆、产出能被同伴看到，由调度 Agent 编排成端到端的港口作业流程。

### 1.2 港航核心业务环节 → Agent 映射

以一艘船从「预报到港」到「离港结算」的全流程拆环节，每个环节一个专家 Agent：

| # | Agent | 业务环节 | 核心职责 | 关联实体 |
|---|---|---|---|---|
| A0 | **DispatchAgent 调度** | 总控 | 拆解作业目标、派活、收口、冲突协调 | 全部 |
| A1 | **BerthAgent 泊位** | 靠泊计划 | 选泊位、排靠泊窗口、潮汐/吃水校验 | berth / vessel / voyage |
| A2 | **CraneAgent 岸桥** | 装卸作业 | 派岸桥、排作业序列、故障改派 | crane / berth |
| A3 | **YardAgent 堆场** | 堆存计划 | 分配箱位、堆场利用率、翻箱优化 | yard / container |
| A4 | **VesselAgent 船务** | 船舶动态 | ETA/ETD 跟踪、航次绑定、船代沟通要点 | vessel / voyage |
| A5 | **CargoAgent 货代** | 货主/单证 | 货主需求、单证齐套、放箱条件 | cargo_owner / container |
| A6 | **ReportAgent 报表** | 作业报告 | 生成日报/航次报告/利用率图表 | 全部（只读汇总）|

> **MVP 范围（v4.4.0）：** A0 调度 + A1 泊位 + A3 堆场 + A4 船务 共 4 个，跑通一条「安排某航次靠泊+堆存」的端到端链路。A2/A5/A6 放 v4.5.0。

### 1.3 明确不做（YAGNI）
- ❌ 不接真实码头 TOS/EDI 系统（本期是决策辅助 Agent，数据来自对话+记忆+用户录入，不做硬集成）。
- ❌ 不做实时船舶 AIS 定位（属外部数据源，留接口不实现）。
- ❌ 不做 Agent 自动学习/强化学习调度策略（规则+LLM 推理即可）。
- ❌ 不重写主 `agent.py`/`main.py`（v4.3.3 已 defer 的独立重构）。

---

## 二、架构设计

### 2.1 分层架构

```
┌──────────────────────────────────────────────────────────┐
│  接入层  ChatPanel / 调度任务视图 (前端 Vue)               │
└───────────────────────────┬──────────────────────────────┘
                            │ /api/orchestration
┌───────────────────────────▼──────────────────────────────┐
│  编排层  MultiAgentOrchestrator (调度 Agent 的执行器)       │
│   - 目标拆解 → subtasks                                    │
│   - 派活给港航 Agent (复用 SubAgentManager.run_parallel)    │
│   - 写 agent_tasks / 收 agent_task_outputs / 共享黑板       │
│   - 冲突检测 (同泊位/同岸桥竞争)                            │
└───────────────────────────┬──────────────────────────────┘
                            │ 注册为新 SubAgentType
┌───────────────────────────▼──────────────────────────────┐
│  Agent 层  港航专家 Agent (都继承 SubAgent 抽象基类)        │
│   BerthAgent / CraneAgent / YardAgent / VesselAgent / ...  │
│   每个: get_system_prompt() 领域提示词 + execute() 推理     │
└───────────────────────────┬──────────────────────────────┘
                            │ 读/写
┌───────────────────────────▼──────────────────────────────┐
│  记忆层 (复用配套方案)                                      │
│   领域记忆: entities(港航type) + memory_relations           │
│   编排记忆: agent_tasks / agent_task_outputs / collab_ctx   │
│   会话记忆: working_contexts (focus_entities)               │
└──────────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策（为什么这么做）

1. **港航 Agent = 扩展 `SubAgentType` 枚举，复用 `SubAgent` 基类。**
   **Why：** 现有 `SubAgentManager` 的派活、provider 注入、tenant override、人格融合全部白拿。新增一个 `BerthAgent(SubAgent)` 只需写 `get_system_prompt()` + `execute()`，约 60 行。不另造 Agent 框架。

2. **调度 Agent 不是子 Agent，是编排器（`MultiAgentOrchestrator`）。**
   **Why：** 子 Agent 是「干活的」，调度是「派活的」，职责不同。调度逻辑放配套方案已设计的 `MultiAgentOrchestrator`，它持有 `SubAgentManager` 派活、持有 `OrchestrationMemory` 落库。

3. **领域知识放提示词 + 领域记忆，不硬编码业务规则。**
   **Why：** 港口规则多变（不同码头潮汐窗口/吃水限制不同），硬编码 if-else 维护地狱。让 Agent 用 `get_system_prompt()` 里的领域知识 + `get_context_for_query()` 取到的实体属性（泊位水深、岸桥外伸距）做推理。

4. **Agent 间协作走共享黑板（`agent_collaboration_ctx`），不直接互调。**
   **Why：** 泊位 Agent 选完 3 号泊位，写 `set_shared(tid, "berth", {...})`；堆场 Agent 读黑板知道船靠 3 号泊位、就近分箱位。松耦合、可追溯、可重放。直接互调会形成 Agent 间硬依赖网。

### 2.3 一次调度时序（以「安排 COSCO123 靠泊+堆存」为例）

```
用户: "安排 COSCO123 明天靠泊卸货 800 箱"
  │
  ▼ MultiAgentOrchestrator.orchestrate()
  ├─ 1. 取领域记忆: get_context_for_query("COSCO123") → "COSCO123 是 COSCO PRIDE 的进口航次, ETA 明日08:00"
  ├─ 2. start_task() → tid
  ├─ 3. 拆解 subtasks (MVP 显式/规则; 后续 LLM):
  │      [berth] 为 COSCO123 选泊位     [vessel] 确认 ETA/吃水
  ├─ 4. run_parallel_tasks(berth, vessel) → 各自 record_output + 可 set_shared
  │      berth → "3号泊位水深16m满足, 明日08-16空闲" → set_shared(berth=3号)
  │      vessel → "吃水14.2m, ETA确认08:00"
  ├─ 5. 串行依赖: yard 读黑板(已知靠3号泊位) → "A区近3号泊位, 分配A12-A19箱位"
  ├─ 6. 冲突检测: 查 agent_collaboration_ctx 是否已有别的航次占3号泊位同窗口
  └─ 7. finish_task(done) → 汇总 outputs 回复用户 + 落 shared 记忆
```

---

## 三、模块拆分

### 3.1 后端模块清单

| 模块 | 文件 | 职责 | 新建/改 |
|---|---|---|---|
| 港航 Agent 类型 | `agent/subagents/base.py` | `SubAgentType` 枚举加 BERTH/CRANE/YARD/VESSEL/CARGO/REPORT | 改 |
| 泊位 Agent | `agent/subagents/port/berth.py` | 靠泊决策 | 新建 |
| 岸桥 Agent | `agent/subagents/port/crane.py` | 装卸派工 | 新建(v4.5) |
| 堆场 Agent | `agent/subagents/port/yard.py` | 堆存分配 | 新建 |
| 船务 Agent | `agent/subagents/port/vessel.py` | 船舶动态 | 新建 |
| 货代 Agent | `agent/subagents/port/cargo.py` | 货主单证 | 新建(v4.5) |
| 报表 Agent | `agent/subagents/port/report.py` | 作业报告 | 新建(v4.5) |
| Agent 注册 | `agent/subagent_manager.py` | `_load_subagents` 注册港航 Agent + 关键词路由 | 改 |
| 调度编排 | `orchestration/multi_agent_orchestrator.py` | 编排+冲突检测 | 配套方案已建,本期扩冲突检测 |
| 编排记忆 | `orchestration/orchestration_memory.py` | 任务/产出/黑板落库 | 配套方案已建 |
| 领域 schema | `memory/domain_schema.py` | 港航实体/关系常量 | 配套方案已建 |
| 港航提示词 | `agent/subagents/port/prompts.py` | 各 Agent 领域提示词集中管理 | 新建 |
| API 路由 | `api/orchestration_routes.py` | 调度任务 CRUD + 触发 | 新建 |

### 3.2 前端模块清单

| 模块 | 文件 | 职责 |
|---|---|---|
| 调度任务视图 | `components/orchestration/OrchestrationTaskView.vue` | 任务列表+详情(派了谁/产出) |
| Agent 状态卡 | `components/orchestration/AgentStatusCard.vue` | 单个港航 Agent 卡片(复用 BaseCard) |
| 调度触发面板 | `components/orchestration/DispatchPanel.vue` | 输入作业目标→触发编排 |
| API client | `api/orchestration.ts` | 调用 /api/orchestration |

---

## 四、目录结构

```
backend/tars/
├── agent/
│   ├── subagents/
│   │   ├── base.py                # 改: SubAgentType 加港航类型
│   │   ├── code.py / writing.py / data.py / research.py / plan.py   # 不动
│   │   └── port/                  # 新建目录: 港航专家 Agent
│   │       ├── __init__.py
│   │       ├── prompts.py         # 各 Agent 领域提示词(集中)
│   │       ├── berth.py           # BerthAgent
│   │       ├── yard.py            # YardAgent
│   │       ├── vessel.py          # VesselAgent
│   │       ├── crane.py           # (v4.5)
│   │       ├── cargo.py           # (v4.5)
│   │       └── report.py          # (v4.5)
│   └── subagent_manager.py        # 改: 注册港航 Agent
├── orchestration/
│   ├── multi_agent_orchestrator.py  # 调度编排器(扩冲突检测)
│   └── orchestration_memory.py      # 编排记忆
├── memory/
│   └── domain_schema.py             # 港航实体/关系常量
└── api/
    └── orchestration_routes.py      # 新建: 调度 API

frontend/src/
├── components/orchestration/        # 新建目录
│   ├── OrchestrationTaskView.vue
│   ├── AgentStatusCard.vue
│   └── DispatchPanel.vue
└── api/orchestration.ts             # 新建

backend/tests/
├── test_port_agents.py              # 港航 Agent 单测
├── test_multi_agent_orchestrator.py # 编排(配套方案已建,本期扩冲突)
└── test_orchestration_memory.py     # 编排记忆(配套方案已建)
```

> **目录原则：** 港航 Agent 全收进 `subagents/port/` 子包，与通用子 Agent 物理隔离，一眼看清「这是垂直领域包」。提示词集中在 `port/prompts.py`，便于领域专家(非程序员)审校口径。

---

## 五、开发规范

### 5.1 港航 Agent 编写规范（每个 Agent 照此模板）

```python
# backend/tars/agent/subagents/port/berth.py
from ..base import SubAgent, SubAgentType
from .prompts import BERTH_PROMPT
from typing import Dict, Any


class BerthAgent(SubAgent):
    """泊位 Agent: 靠泊计划决策。"""

    def __init__(self, llm_provider=None):
        super().__init__(SubAgentType.BERTH, llm_provider)

    def get_system_prompt(self) -> str:
        return BERTH_PROMPT

    async def execute(self, task: str, context: Dict[str, Any] = None) -> str:
        from ....models.base import ChatMessage
        ctx = context or {}
        # 领域记忆 + 共享黑板拼进 user 消息(只读, 不改基类签名)
        domain = ctx.get("domain_memory", "")
        shared = ctx.get("shared", {})
        prompt = self.merge_with_personality(ctx.get("personality"))
        user_content = f"领域记忆:\n{domain}\n\n协作黑板:\n{shared}\n\n任务:\n{task}"
        if self.llm_provider:
            resp = await self.llm_provider.chat(
                [ChatMessage(role="system", content=prompt),
                 ChatMessage(role="user", content=user_content)], stream=False)
            return resp.content if hasattr(resp, "content") else str(resp)
        return f"[泊位] 待 LLM: {task}"
```

**强制规范：**
1. **必须继承 `SubAgent`**，实现 `get_system_prompt()` + `execute()` 两个抽象方法。
2. **提示词写在 `port/prompts.py`**，不内联在 Agent 类里（便于业务审校）。
3. **`execute()` 不改基类签名** `(task, context)`，领域记忆/黑板通过 `context` 字典传入。
4. **不在 Agent 里直接写数据库**，落库由编排器 `OrchestrationMemory` 统一做（Agent 只返回字符串产出）。
5. **每个 Agent 配一条单测**：mock `llm_provider`，断言 `get_system_prompt()` 含关键领域词 + `execute()` 能把 domain/shared 拼进 prompt。

### 5.2 提示词规范（`port/prompts.py`）

每个 Agent 提示词四段式：**角色定位 → 领域知识 → 决策原则 → 输出格式**。例：

```python
BERTH_PROMPT = """你是港口泊位调度专家。
## 领域知识
- 靠泊三要素: 泊位水深 ≥ 船舶吃水 + 富裕水深(通常1m); 泊位长度 ≥ 船长 × 1.1; 靠泊窗口不与其他航次冲突
- 潮汐: 大型船需在高潮位窗口进出港
## 决策原则
- 优先满足硬约束(水深/长度), 再优化(靠近目标堆场、减少岸桥移动)
- 冲突时给出备选泊位 + 理由
## 输出格式
- 推荐泊位 + 靠泊窗口(起止时间) + 校验依据(水深/长度) + 备选方案
- 缺数据时明确指出需要补充什么(如船舶吃水)"""
```

### 5.3 通用规范
- **TDD**：先写失败测试，再实现，每 Task 一次提交（参考配套方案的步骤粒度）。
- **不删/不动现有 5 个通用子 Agent。** 港航 Agent 是新增。
- **新增接口默认参数保持向后兼容**（不传 = 旧行为）。
- **动库前备份** `tars.db`，新枚举值不影响旧数据。
- **提交信息**：`feat(port-agent): ...` / `feat(orchestration): ...` 前缀。
- **分支**：`feat/v4.4.0-port-agents`。

---

## 六、任务排期

### Phase A — 前置依赖（来自配套记忆方案，必须先完成）
| Task | 内容 | 工期 |
|---|---|:---:|
| A | 配套方案 Phase 0-3：降级开关 + 港航实体 schema + 共享记忆层(3表) + OrchestrationMemory + MultiAgentOrchestrator | 4d |

> 本文件的港航 Agent 强依赖共享记忆层。**先做完配套方案 Phase 0-3 再开本文件 Phase B。**

### Phase B — 港航 Agent 骨架（2 天）
| Task | 内容 | 文件 | 工期 |
|---|---|---|:---:|
| B1 | `SubAgentType` 加 BERTH/YARD/VESSEL(+CRANE/CARGO/REPORT 预留) | `subagents/base.py` | 0.3d |
| B2 | 建 `port/` 包 + `prompts.py`(BERTH/YARD/VESSEL 三段提示词) | `subagents/port/` | 0.5d |
| B3 | 写 BerthAgent / YardAgent / VesselAgent(套 5.1 模板) | `port/berth.py` 等 | 0.7d |
| B4 | `SubAgentManager._load_subagents` 注册三个港航 Agent + 关键词路由(泊位/靠泊/堆场/船) | `subagent_manager.py` | 0.5d |

### Phase C — 编排接入（2 天）
| Task | 内容 | 工期 |
|---|---|:---:|
| C1 | `MultiAgentOrchestrator` 加目标拆解(MVP 规则: 命中港航关键词→生成对应 subtasks) | 0.7d |
| C2 | 串行依赖支持: yard 在 berth 之后跑、读黑板 | 0.5d |
| C3 | 冲突检测: 同泊位/同窗口竞争查 `agent_collaboration_ctx` 告警 | 0.8d |

### Phase D — API + 前端（2 天）
| Task | 内容 | 工期 |
|---|---|:---:|
| D1 | `orchestration_routes.py`: GET tasks / GET task detail / POST dispatch | 0.7d |
| D2 | `OrchestrationTaskView.vue` + `AgentStatusCard.vue`(复用 BaseCard/EmptyState) | 0.8d |
| D3 | `DispatchPanel.vue` 触发面板 + `orchestration.ts` client | 0.5d |

### Phase E — 端到端验收（1 天）
| Task | 内容 | 工期 |
|---|---|:---:|
| E1 | 端到端集成测: "安排 COSCO123 靠泊+堆存" 跑通全链路 | 0.5d |
| E2 | 浏览器手测调度视图 + 回归(普通对话不受影响) | 0.5d |

**总工期：** 配套方案 4d + 本文件 B~E 7d = **约 11 人天**。
**里程碑：** Phase B+C 完成 = 后端 MVP 可跑；Phase D 完成 = 有界面；Phase E = 可演示。

---

## 七、关键 Task 详化（B1/B3/C1，给执行者直接照做）

### Task B1：扩 SubAgentType 枚举
**Files:** Modify `backend/tars/agent/subagents/base.py:10`

```python
class SubAgentType(Enum):
    CODE = "code"
    WRITING = "writing"
    DATA = "data"
    RESEARCH = "research"
    PLAN = "plan"
    # v4.4.0 港航
    BERTH = "berth"
    YARD = "yard"
    VESSEL = "vessel"
    CRANE = "crane"      # v4.5 预留
    CARGO = "cargo"      # v4.5 预留
    REPORT = "report"    # v4.5 预留
```
同时在 `_get_default_config` 的 configs 字典补三条（name/description/temperature=0.3，决策要稳）。
**验收：** `python -c "from tars.agent.subagents.base import SubAgentType; print(SubAgentType.BERTH.value)"` → `berth`

### Task B3：BerthAgent（其余 Agent 同模板，改提示词+类型即可，不复述）
按 §5.1 模板写。**单测：**
```python
def test_berth_agent_prompt():
    from tars.agent.subagents.port.berth import BerthAgent
    a = BerthAgent()
    assert "泊位" in a.get_system_prompt() and "水深" in a.get_system_prompt()
```
Run: `cd backend && python -m pytest tests/test_port_agents.py::test_berth_agent_prompt -v` → PASS

### Task C1：目标拆解（MVP 规则版）
**Files:** Modify `multi_agent_orchestrator.py`，加 `_decompose(goal) -> list[subtask]`：
```python
def _decompose(self, goal: str) -> list:
    g = goal.lower()
    subs = []
    if any(k in g for k in ["靠泊", "泊位", "berth", "靠"]):
        subs.append({"agent_type": "berth", "task": f"为目标选泊位: {goal}"})
    if any(k in g for k in ["卸", "装", "堆", "箱", "yard"]):
        subs.append({"agent_type": "yard", "task": f"分配堆场箱位: {goal}"})
    if any(k in g for k in ["船", "航次", "eta", "vessel"]):
        subs.append({"agent_type": "vessel", "task": f"确认船舶动态: {goal}"})
    return subs or [{"agent_type": "research", "task": goal}]
```
**Why MVP 用规则：** 先跑通编排闭环，LLM 自动拆解放迭代（避免一上来就调 LLM 拆解、不可控）。
**验收：** `_decompose("安排COSCO123靠3号泊位卸800箱")` 返回 berth+yard 两个 subtask。

---

## 八、风险与对策

| 风险 | 对策 |
|---|---|
| 港航领域提示词口径不准（程序员不懂业务） | 提示词集中 `port/prompts.py`，交港口业务专家审校后再上线 |
| Agent 间串行依赖（yard 等 berth）拖慢响应 | 仅强依赖串行，其余并行；超时单 Agent 降级返回"待补充" |
| 冲突检测误报/漏报 | MVP 只做同泊位同窗口的硬冲突告警，软优化留后续 |
| 没有真实码头数据，Agent 产出"看起来对但没数据" | Agent 缺数据时必须显式输出"需要补充 X"，不编造（写进提示词输出规范） |
| 新枚举值影响旧 `_determine_agent_type` 路由 | 港航关键词与通用关键词不重叠；加单测覆盖路由 |

---

## 九、执行前自检
- [ ] 配套记忆方案 Phase 0-3 已完成（共享记忆层就绪）
- [ ] 在新分支 `feat/v4.4.0-port-agents`
- [ ] 已备份 `tars.db`
- [ ] 港航提示词已请业务专家过一遍口径
- [ ] 每个港航 Agent 有单测、编排有端到端测
- [ ] 全程不碰 `agent.py`/`main.py` 硬拆分、不动现有 5 个通用子 Agent
