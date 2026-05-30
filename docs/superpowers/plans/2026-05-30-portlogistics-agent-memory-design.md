---
doc_type: plan
status: shipped
platform_version: v4.4.0
---

# 港航物流垂直 Agent · 记忆与多 Agent 调度融合设计方案

> **给执行者（牛马）的话：** 本文件是**设计蓝图**，不是要你照抄的代码。每个模块给了：要改哪个文件、表结构 DDL、接口签名、为什么这么设计、怎么验收。按 Phase 顺序做，每个 Task 做完能独立跑通、能测、能提交。遇到与现状冲突的，**以现状代码为准**，先问再改。
>
> 日期：2026-05-30
> 版本目标：v4.4.0 「港航垂直 + 多 Agent 调度」
> 作者：架构（Claude） / 执行：实现团队

---

## 〇、为什么不照搬 `2026-05-30-memory-simplify-plan.md`

那份精简方案是**通用 SaaS 思路**：删实体层、删图谱、用规则匹配做提取。它对"普通问答助手"是对的，但对**港航物流垂直 + 调度多 Agent** 是错的，原因有三：

| 精简方案做法 | 在港航垂直场景的问题 |
|---|---|
| 删掉 `entities` / `memory_relations` / 实体树 | 港航是**强实体领域**：码头、泊位、岸桥、船舶、航次、堆场、货主之间是网状关系。删了实体层，"QC-7 上月故障"这种记忆就只能全文搜，关联不到"它属于元洪码头、影响了 COSCO123 航次"。**实体层是垂直化的地基，必须留。** |
| 用 `extractor.py` 规则匹配代替 LLM 提取 | 规则能抓"我喜欢简洁回答"，但抓不到"QC-7 大梁裂纹导致 3 号泊位停摆"这种领域语义。**垂直领域提取必须保留 LLM 路径。** |
| 完全没有"Agent 之间共享记忆"概念 | 调度多 Agent 的**核心就是共享上下文**：调度 Agent 派活给堆场 Agent，堆场 Agent 的产出必须能被船务 Agent 读到。精简方案对此零设计。 |

**正确策略 = 融合，不是精简：**
1. **保留**实体层（垂直地基）+ LLM 提取（垂直语义）。
2. **降级**真正与推理无关的周边（compressor / kb_promotion / turn_knowledge_publisher / tree_builder），用已有的 `MemoryConfig` env 开关关掉，**代码不删**，需要时一行开关打开。
3. **新增**多 Agent 编排记忆层（当前完全不存在）。
4. **新增**港航领域实体 schema（在现有 `entities` 表上扩展 type，零迁移）。

---

## 一、现状盘点（执行前必读，已核对代码）

### 已有、要复用的
| 资产 | 位置 | 说明 |
|---|---|---|
| `memories` 表 | `connection.py:78` | 主记忆表，有 `tenant_id` / `scope`('private'\|'shared') / `entity_refs` / `embedding` / FTS5 |
| `entities` 表 | `connection.py:443` | `id/type/name/aliases/attributes(JSON)/confidence`。**type 是自由字符串，加港航类型零迁移** |
| `memory_entity_links` 表 | `connection.py:459` | 记忆↔实体多对多 |
| `memory_relations` 表 | `connection.py:469` | 实体↔实体（source_id/target_id/relation_type/weight）|
| `working_contexts` 表 | `connection.py:210` | 会话级：focus_entities / current_intent / open_threads / active_skills |
| `MemoryManager.for_tenant(tid)` | `memory/manager.py:50` | 多租户记忆入口 |
| `SubAgentManager` | `agent/subagent_manager.py:14` | 5 个子 Agent + `delegate_task` / `run_parallel_tasks` |
| `HandoffManager` | `agent/handoff.py:40` | 子 Agent 交接（**仅内存，不落库**）|
| `MemoryConfig` env 开关 | `config/memory.py:7` | `get_bool_env("TARS_XXX", default)` 模式，周边降级就用它 |
| `modules.yaml` | `backend/config/modules.yaml` | 模块开关清单 |

### 缺口（本方案要补的）
1. **Agent 之间完全隔离**：`SubAgentManager.run_parallel_tasks` 跑完结果不落库，子 Agent 看不到彼此产出，也读不到主记忆。
2. **Handoff 不落库**：`HandoffManager` 重启即丢，无法审计、无法追溯调度链。
3. **没有编排记忆**：没有"一次调度任务 → 派了哪些 Agent → 各自产出 → 汇总"的持久结构。
4. **没有港航领域实体类型**：`entities.type` 还是通用 person/org/concept。

---

## 二、目标架构（一张图）

```
                          ┌─────────────────────────────┐
   用户 "安排 COSCO123  →  │   调度 Agent (Orchestrator) │
   靠 3 号泊位卸货"        │   读 working_context +      │
                          │   实体图谱 + 编排记忆        │
                          └───────────┬─────────────────┘
                                      │ 派活 (落 agent_tasks)
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
       ┌────────────┐         ┌────────────┐         ┌────────────┐
       │ 泊位 Agent  │         │ 堆场 Agent  │         │ 船务 Agent  │
       │ (子Agent)   │         │ (子Agent)   │         │ (子Agent)   │
       └─────┬──────┘         └─────┬──────┘         └─────┬──────┘
             │ 产出落 agent_task_outputs (scope=shared)     │
             └───────────────┬───────────────┬─────────────┘
                             ▼               ▼
              ┌──────────────────────────────────────────┐
              │  共享记忆层 (本方案核心新增)                │
              │  ├ agent_tasks         (一次调度 = 一行)   │
              │  ├ agent_task_outputs  (每个子Agent产出)   │
              │  └ collaboration_ctx   (调度链共享黑板)    │
              └──────────────────┬───────────────────────┘
                                 ▼
              ┌──────────────────────────────────────────┐
              │  领域记忆层 (复用现有，加港航 type)         │
              │  memories + entities(港航type) + relations │
              └──────────────────────────────────────────┘
                                 ▼
              ┌──────────────────────────────────────────┐
              │  降级层 (env 关掉，代码不删)               │
              │  compressor / kb_promotion / tree_builder │
              │  / turn_knowledge_publisher               │
              └──────────────────────────────────────────┘
```

---

## 三、Phase 0 — 周边降级（先做，最快见效，0.5 天）

**目标：** 不删代码，用开关关掉与推理无关的周边，立即降低延迟和维护面。**所有开关默认值改为"垂直模式关闭"，需要时一行打开。**

### Task 0.1：在 MemoryConfig 增加垂直模式开关

**Files:**
- Modify: `backend/tars/config/memory.py`

- [ ] **Step 1：在 `MemoryConfig.__init__` 末尾追加开关**

```python
        # v4.4.0 垂直模式：周边降级开关（默认关，需要时设 env=true 打开）
        self.compressor_enabled = get_bool_env("TARS_MEMORY_COMPRESSOR", False)
        self.kb_promotion_enabled = get_bool_env("TARS_KB_PROMOTION", False)
        self.tree_builder_enabled = get_bool_env("TARS_MEMORY_TREE_BUILDER", False)
        self.turn_publisher_enabled = get_bool_env("TARS_TURN_PUBLISHER", False)
```

- [ ] **Step 2：找到调用方，包一层开关。** grep 出调用点：

Run: `grep -rn "compressor\|kb_promotion\|tree_builder\|turn_knowledge_publisher" backend/tars/ --include=*.py | grep -v "config/memory.py\|__pycache__\|def \|class \|import"`

对每个调用点，包成 `if config.xxx_enabled:`。**不要删函数定义，只在调用处加守卫。**

- [ ] **Step 3：验收。** 启动后端，发一条普通消息，确认日志里没有 compressor/kb_promotion 的执行记录，且对话正常返回。

Run: `cd backend && python -c "from tars.config.memory import config; print('compressor',config.compressor_enabled,'kb',config.kb_promotion_enabled,'tree',config.tree_builder_enabled,'pub',config.turn_publisher_enabled)"`
Expected: 全部 `False`

- [ ] **Step 4：提交**

```bash
git add backend/tars/config/memory.py
git commit -m "feat(memory): add vertical-mode degradation switches for周边 modules"
```

> **为什么不删：** 这些模块（知识库晋升、压缩、实体树可视化）在"通用助手"或"个人知识库"形态下有用。垂直港航 MVP 用不到，但保留开关 = 零成本可逆。删了将来想加回来要重写。

---

## 四、Phase 1 — 港航领域实体建模（1 天）

**目标：** 在现有 `entities` 表上定义港航实体类型 + 关系类型，**不改表结构**（type 本就是自由字符串），只加一个领域 schema 常量文件 + 提取提示词。

### Task 1.1：定义港航实体 / 关系类型常量

**Files:**
- Create: `backend/tars/memory/domain_schema.py`

- [ ] **Step 1：写常量文件**

```python
"""港航物流领域实体/关系 schema (v4.4.0)。
entities.type 复用现有自由字符串列，无需迁移。"""

# 实体类型
ENTITY_TERMINAL = "terminal"        # 码头  e.g. 元洪码头
ENTITY_BERTH = "berth"              # 泊位  e.g. 3号泊位
ENTITY_CRANE = "crane"              # 岸桥  e.g. QC-7
ENTITY_VESSEL = "vessel"            # 船舶  e.g. COSCO PRIDE
ENTITY_VOYAGE = "voyage"            # 航次  e.g. COSCO123
ENTITY_YARD = "yard"                # 堆场  e.g. A区堆场
ENTITY_CARGO_OWNER = "cargo_owner"  # 货主  e.g. 中远海运
ENTITY_CONTAINER = "container"      # 集装箱组/箱

PORT_ENTITY_TYPES = [
    ENTITY_TERMINAL, ENTITY_BERTH, ENTITY_CRANE, ENTITY_VESSEL,
    ENTITY_VOYAGE, ENTITY_YARD, ENTITY_CARGO_OWNER, ENTITY_CONTAINER,
]

# 关系类型 (memory_relations.relation_type)
REL_BERTH_OF = "berth_of"            # 泊位 → 码头
REL_CRANE_SERVES = "crane_serves"    # 岸桥 → 泊位
REL_VOYAGE_OF = "voyage_of"          # 航次 → 船舶
REL_VOYAGE_BERTHS_AT = "berths_at"   # 航次 → 泊位
REL_YARD_OF = "yard_of"              # 堆场 → 码头
REL_CARGO_OF = "cargo_of"            # 货主 → 航次

PORT_RELATION_TYPES = [
    REL_BERTH_OF, REL_CRANE_SERVES, REL_VOYAGE_OF,
    REL_VOYAGE_BERTHS_AT, REL_YARD_OF, REL_CARGO_OF,
]
```

- [ ] **Step 2：建议属性约定（写进 docstring，不强制）**

```python
# attributes(JSON) 建议字段：
#   berth:   {"length_m": 300, "depth_m": 16, "status": "free|occupied|maintenance"}
#   crane:   {"model": "QC", "outreach_m": 65, "status": "running|fault|idle"}
#   voyage:  {"eta": "ISO8601", "etd": "ISO8601", "direction": "import|export"}
#   vessel:  {"loa_m": 366, "imo": "..."}
```

- [ ] **Step 3：提交**

```bash
git add backend/tars/memory/domain_schema.py
git commit -m "feat(memory): add port-logistics domain entity/relation schema"
```

### Task 1.2：让提取器认识港航类型

**Files:**
- Modify: `backend/tars/memory/extractor.py`（实体提取提示词处；先 grep 定位）

- [ ] **Step 1：定位提取提示词**

Run: `grep -n "type\|prompt\|实体\|entity" backend/tars/memory/extractor.py | head -20`

- [ ] **Step 2：把 `PORT_ENTITY_TYPES` 注入提取提示词**，让 LLM 抽取时优先归类到港航类型。示例片段（按实际提示词结构插入）：

```python
from .domain_schema import PORT_ENTITY_TYPES
# ... 在构造提示词时：
f"优先将实体归类为以下港航类型之一（不匹配再用通用类型）：{', '.join(PORT_ENTITY_TYPES)}"
```

- [ ] **Step 3：验收（手测一条）**

Run: `cd backend && python -c "import asyncio; from tars.memory.manager import MemoryManager; from tars.database.base import Database; m=MemoryManager(db=Database()).for_tenant('default'); asyncio.run(m.add_manual_memory('QC-7 岸桥大梁裂纹，影响元洪码头3号泊位', category='project_record'))"`
然后查实体表：
Run: `cd backend && python -c "from tars.database.base import Database; db=Database(); print(db.fetch_all('SELECT type,name FROM entities ORDER BY created_at DESC LIMIT 5'))"`
Expected: 出现 type=crane/terminal/berth 的实体（若 LLM 提取开启）

- [ ] **Step 4：提交**

```bash
git add backend/tars/memory/extractor.py
git commit -m "feat(memory): bias entity extraction toward port-logistics types"
```

---

## 五、Phase 2 — 多 Agent 共享记忆层（核心，2 天）

**目标：** 新增 3 张表 + 一个 `OrchestrationMemory` 服务，让"一次调度任务 → 多个子 Agent 产出 → 共享黑板"全程落库、可追溯、子 Agent 互相可见。

### Task 2.1：建表

**Files:**
- Modify: `backend/tars/database/connection.py`（在实体表之后追加，约 line 510 后）

- [ ] **Step 1：在 `connection.py` 追加三张表 DDL**

```python
        # v4.4.0 多 Agent 编排记忆
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                session_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',  -- running|done|failed
                orchestrator TEXT NOT NULL DEFAULT 'master',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_task_outputs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,        -- code|writing|data|research|plan|港航子agent
                subtask TEXT NOT NULL,
                output TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'done',  -- done|failed
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_collaboration_ctx (
                task_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,             -- JSON，子Agent间共享的黑板
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (task_id, key)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_outputs_task ON agent_task_outputs(task_id)")
```

- [ ] **Step 2：验收建表**

Run: `cd backend && python -c "from tars.database.base import Database; db=Database(); print([r['name'] for r in db.fetch_all(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'agent_%'\")])"`
Expected: `['agent_tasks', 'agent_task_outputs', 'agent_collaboration_ctx']`

- [ ] **Step 3：提交**

```bash
git add backend/tars/database/connection.py
git commit -m "feat(db): add multi-agent orchestration memory tables"
```

### Task 2.2：OrchestrationMemory 服务

**Files:**
- Create: `backend/tars/orchestration/orchestration_memory.py`
- Test: `backend/tests/test_orchestration_memory.py`

- [ ] **Step 1：先写失败测试**

```python
import uuid
from tars.database.base import Database
from tars.orchestration.orchestration_memory import OrchestrationMemory

def test_task_lifecycle():
    om = OrchestrationMemory(db=Database(db_path=":memory:"))
    tid = om.start_task(session_id="s1", goal="安排COSCO123靠泊")
    om.record_output(tid, agent_type="berth", subtask="选泊位", output="3号泊位空闲")
    om.record_output(tid, agent_type="yard", subtask="选堆场", output="A区可用")
    om.set_shared(tid, "berth_choice", {"berth": "3号"}, by="berth")
    outs = om.get_outputs(tid)
    assert len(outs) == 2
    assert om.get_shared(tid)["berth_choice"]["berth"] == "3号"
    om.finish_task(tid, status="done")
    assert om.get_task(tid)["status"] == "done"
```

- [ ] **Step 2：运行确认失败**

Run: `cd backend && python -m pytest tests/test_orchestration_memory.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3：实现服务（最小实现）**

```python
"""多 Agent 编排记忆：一次调度任务的产出与共享黑板落库。"""
import json
import uuid
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat()


class OrchestrationMemory:
    def __init__(self, db, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id

    def start_task(self, session_id: str, goal: str, orchestrator: str = "master") -> str:
        tid = str(uuid.uuid4())
        now = _now()
        self.db.execute(
            "INSERT INTO agent_tasks (id,tenant_id,session_id,goal,status,orchestrator,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (tid, self.tenant_id, session_id, goal, "running", orchestrator, now, now),
        )
        return tid

    def record_output(self, task_id: str, agent_type: str, subtask: str, output: str, status: str = "done"):
        self.db.execute(
            "INSERT INTO agent_task_outputs (id,task_id,agent_type,subtask,output,status,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), task_id, agent_type, subtask, output, status, _now()),
        )

    def get_outputs(self, task_id: str) -> list:
        return self.db.fetch_all(
            "SELECT agent_type,subtask,output,status FROM agent_task_outputs WHERE task_id=? ORDER BY created_at",
            (task_id,),
        )

    def set_shared(self, task_id: str, key: str, value, by: str):
        self.db.execute(
            "INSERT INTO agent_collaboration_ctx (task_id,key,value,updated_by,updated_at)"
            " VALUES (?,?,?,?,?) ON CONFLICT(task_id,key) DO UPDATE SET value=excluded.value,"
            " updated_by=excluded.updated_by, updated_at=excluded.updated_at",
            (task_id, key, json.dumps(value, ensure_ascii=False), by, _now()),
        )

    def get_shared(self, task_id: str) -> dict:
        rows = self.db.fetch_all(
            "SELECT key,value FROM agent_collaboration_ctx WHERE task_id=?", (task_id,)
        )
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def finish_task(self, task_id: str, status: str = "done"):
        self.db.execute(
            "UPDATE agent_tasks SET status=?, updated_at=? WHERE id=?",
            (status, _now(), task_id),
        )

    def get_task(self, task_id: str) -> dict:
        return self.db.fetch_one("SELECT * FROM agent_tasks WHERE id=?", (task_id,))
```

> **注意：** 先 grep 确认 `Database` 的实际方法名是 `execute` / `fetch_all` / `fetch_one`。若不同，按现状调整。
> Run: `grep -n "def execute\|def fetch_all\|def fetch_one" backend/tars/database/base.py`

- [ ] **Step 4：运行确认通过**

Run: `cd backend && python -m pytest tests/test_orchestration_memory.py -v`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add backend/tars/orchestration/orchestration_memory.py backend/tests/test_orchestration_memory.py
git commit -m "feat(orchestration): add OrchestrationMemory for multi-agent shared memory"
```

### Task 2.3：把 SubAgentManager 接入编排记忆

**Files:**
- Modify: `backend/tars/agent/subagent_manager.py`（`run_parallel_tasks` 处，line 197）

- [ ] **Step 1：让 `run_parallel_tasks` 接受可选 `orchestration_memory` 并把每个子任务产出落库**

```python
    async def run_parallel_tasks(self, tasks: list, context: Dict[str, Any] = None,
                                  orch_mem=None, task_id: str = None) -> dict:
        async def run_task(task_info):
            agent_type = task_info.get("agent_type")
            subtask = task_info.get("task", "")
            result = await self.invoke_subagent(agent_type, subtask, context)
            if orch_mem and task_id:
                orch_mem.record_output(task_id, agent_type=agent_type, subtask=subtask, output=result)
            return {agent_type: result}
        # ... 保留原有 asyncio.gather 逻辑，把上面的 run_task 用进去
```

> **关键：** 不要破坏现有签名的默认行为——`orch_mem` / `task_id` 都默认 None，不传时行为与现在完全一致。

- [ ] **Step 2：让子 Agent 能读共享黑板。** 在 `run_task` 调用前，把 `orch_mem.get_shared(task_id)` 注入 `context`：

```python
            if orch_mem and task_id:
                context = {**(context or {}), "shared": orch_mem.get_shared(task_id)}
```

- [ ] **Step 3：验收（集成测一条）**

```python
# 追加到 tests/test_orchestration_memory.py
import asyncio
from tars.agent.subagent_manager import SubAgentManager

def test_parallel_persists_outputs():
    db = Database(db_path=":memory:")
    om = OrchestrationMemory(db=db)
    tid = om.start_task("s1", "并行选泊位和堆场")
    mgr = SubAgentManager()
    asyncio.run(mgr.run_parallel_tasks(
        [{"agent_type": "research", "task": "查3号泊位状态"}],
        orch_mem=om, task_id=tid))
    assert len(om.get_outputs(tid)) >= 1
```

Run: `cd backend && python -m pytest tests/test_orchestration_memory.py::test_parallel_persists_outputs -v`
Expected: PASS（若子 Agent 需要 LLM provider，可 mock 或标记为 integration 跳过——按现有测试约定处理）

- [ ] **Step 4：提交**

```bash
git add backend/tars/agent/subagent_manager.py backend/tests/test_orchestration_memory.py
git commit -m "feat(agent): wire SubAgentManager outputs into OrchestrationMemory"
```

### Task 2.4：Handoff 落库

**Files:**
- Modify: `backend/tars/agent/handoff.py`（`HandoffManager`，line 40）

- [ ] **Step 1：给 `HandoffManager.__init__` 加可选 `db`，在 `create_pending` / `accept` / `reject` 时落库到 `approval_requests` 表（已存在，见 `connection.py:249`，结构完全够用，复用即可，不新建表）。**

```python
    def __init__(self, preview_limit: int = 500, db=None):
        self._items = {}
        self._db = db
        self._preview_limit = preview_limit
```

在 `create_pending` 末尾：
```python
        if self._db:
            self._db.execute(
                "INSERT INTO approval_requests (id,tenant_id,user_id,session_id,tool_name,arguments,status,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (handoff.id, tenant_id, user_id, session_id, "subagent_handoff",
                 json.dumps(handoff.to_ws_payload(), ensure_ascii=False), "pending", _now_local().isoformat()),
            )
```
`accept` / `reject` 时 `UPDATE approval_requests SET status=?, resolved_at=? WHERE id=?`。

> **为什么复用 `approval_requests` 而不新建表：** 它本就是"待人工审批"语义，字段（tool_name/arguments/status/resolved_at/resolved_by）完全覆盖 handoff 需求。新建表是重复造轮子。

- [ ] **Step 2：验收**

Run: `cd backend && python -m pytest tests/ -k handoff -v`（若无现成测试，新写一条：create_pending 后查 approval_requests 有一行 status=pending）
Expected: PASS

- [ ] **Step 3：提交**

```bash
git add backend/tars/agent/handoff.py
git commit -m "feat(agent): persist subagent handoffs to approval_requests table"
```

---

## 六、Phase 3 — 调度 Agent（Orchestrator）串起来（1.5 天）

**目标：** 一个总调度 Agent：拆解用户目标 → 派给子 Agent（落 `agent_tasks`）→ 收集产出 → 读实体图谱补充上下文 → 汇总回复。

### Task 3.1：MultiAgentOrchestrator

**Files:**
- Create: `backend/tars/orchestration/multi_agent_orchestrator.py`
- Test: `backend/tests/test_multi_agent_orchestrator.py`

- [ ] **Step 1：失败测试**

```python
import asyncio
from tars.database.base import Database
from tars.orchestration.multi_agent_orchestrator import MultiAgentOrchestrator

def test_orchestrate_records_task():
    orch = MultiAgentOrchestrator(db=Database(db_path=":memory:"))
    result = asyncio.run(orch.orchestrate(
        session_id="s1",
        goal="安排COSCO123靠3号泊位卸货",
        subtasks=[{"agent_type": "research", "task": "查3号泊位状态"}],
    ))
    assert "task_id" in result
    assert result["status"] == "done"
```

- [ ] **Step 2：运行确认失败**

Run: `cd backend && python -m pytest tests/test_multi_agent_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3：实现（最小，编排逻辑显式传入 subtasks，拆解策略后续迭代）**

```python
"""总调度 Agent：派活给子 Agent，全程落编排记忆。"""
from .orchestration_memory import OrchestrationMemory
from ..agent.subagent_manager import SubAgentManager


class MultiAgentOrchestrator:
    def __init__(self, db, tenant_id: str = "default", subagent_manager=None):
        self.db = db
        self.mem = OrchestrationMemory(db=db, tenant_id=tenant_id)
        self.subagents = subagent_manager or SubAgentManager()

    async def orchestrate(self, session_id: str, goal: str, subtasks: list) -> dict:
        task_id = self.mem.start_task(session_id=session_id, goal=goal)
        try:
            await self.subagents.run_parallel_tasks(
                subtasks, orch_mem=self.mem, task_id=task_id)
            self.mem.finish_task(task_id, status="done")
            return {"task_id": task_id, "status": "done",
                    "outputs": self.mem.get_outputs(task_id),
                    "shared": self.mem.get_shared(task_id)}
        except Exception as e:
            self.mem.finish_task(task_id, status="failed")
            return {"task_id": task_id, "status": "failed", "error": str(e)}
```

- [ ] **Step 4：运行确认通过**

Run: `cd backend && python -m pytest tests/test_multi_agent_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5：提交**

```bash
git add backend/tars/orchestration/multi_agent_orchestrator.py backend/tests/test_multi_agent_orchestrator.py
git commit -m "feat(orchestration): add MultiAgentOrchestrator with persisted task memory"
```

### Task 3.2：把领域记忆喂给调度 Agent

**Files:**
- Modify: `backend/tars/orchestration/multi_agent_orchestrator.py`

- [ ] **Step 1：`orchestrate` 开头，用 `MemoryManager.for_tenant(tid).get_context_for_query(goal)` 取领域上下文，注入子任务 context**

```python
        from ..memory.manager import MemoryManager
        ctx = MemoryManager(db=self.db).for_tenant(self.tenant_id).get_context_for_query(goal)
        for st in subtasks:
            st.setdefault("context", {})["domain_memory"] = ctx
```

> **为什么：** 这是垂直化的关键闭环——调度 QC-7 故障时，子 Agent 能看到"QC-7 属于元洪码头、上月已故障一次"的领域记忆，而不是从零开始。

- [ ] **Step 2：验收 + 提交**

Run: `cd backend && python -m pytest tests/test_multi_agent_orchestrator.py -v`
Expected: PASS

```bash
git add backend/tars/orchestration/multi_agent_orchestrator.py
git commit -m "feat(orchestration): inject domain memory context into subtasks"
```

---

## 七、Phase 4 — 前端最小可视（1 天，可选，MVP 后做）

**目标：** 不动现有 7-tab 记忆视图（那是另一条精简线），只新增一个"调度任务"视图，看一次调度派了哪些 Agent、各自产出。

### Task 4.1：调度任务列表 API + 视图

**Files:**
- Create: `backend/tars/api/orchestration_routes.py`（`GET /api/orchestration/tasks`、`GET /api/orchestration/tasks/{id}`）
- Create: `frontend/src/components/orchestration/OrchestrationTaskView.vue`

- [ ] **Step 1：API 返回 `agent_tasks` + 关联 `agent_task_outputs`**（只读，分页）。
- [ ] **Step 2：前端列表 + 详情抽屉**，展示 goal / status / 每个子 Agent 的 subtask+output。复用 v4.3.4 的 `BaseCard` / `EmptyState`。
- [ ] **Step 3：注册路由到 `modules.yaml` optional 段**（参考 meeting/bi 的写法），默认 `enabled: true`。
- [ ] **Step 4：`npm run build` 通过 + 浏览器手测一次调度任务可见。**
- [ ] **Step 5：提交。**

---

## 八、实施顺序与里程碑

| Phase | 内容 | 工期 | 产出物 | 能独立验收？ |
|---|---|:---:|---|:---:|
| 0 | 周边降级开关 | 0.5d | env 开关 + 调用守卫 | ✅ 对话仍正常、延迟降 |
| 1 | 港航实体建模 | 1d | domain_schema.py + 提取偏置 | ✅ 提取出港航 type 实体 |
| 2 | 共享记忆层 | 2d | 3 表 + OrchestrationMemory + handoff 落库 | ✅ 产出/黑板可落库可读 |
| 3 | 调度 Agent | 1.5d | MultiAgentOrchestrator | ✅ 一次调度全程可追溯 |
| 4 | 前端可视 | 1d | 调度任务视图 | ✅ 浏览器可见调度链 |

**总工期约 6 人天。** Phase 0→3 是后端闭环，做完就是可用的「垂直 + 调度」MVP；Phase 4 是锦上添花。

---

## 九、与现状的兼容性保证（给执行者的红线）

1. **所有新增对外接口都默认不影响旧行为**：`run_parallel_tasks` 的 `orch_mem`/`task_id`、`HandoffManager` 的 `db` 全是可选参数，不传时 = 现状。
2. **不删任何周边模块代码**，只加 env 守卫。回退 = 改一个 env。
3. **不改 `entities` 表结构**，港航类型走自由字符串 type。
4. **复用 `approval_requests` 表**承载 handoff，不新建审批表。
5. **动库前先备份**：`cp backend/data/tars.db backend/data/tars.db.bak.$(date +%s)`。
6. **每个 Task 独立提交**，出问题可单点回退。

---

## 十、明确不做（YAGNI）

- ❌ 不做调度 Agent 的"自动拆解目标"（LLM 自动把 goal 拆成 subtasks）——MVP 阶段 subtasks 显式传入，验证闭环后再迭代。
- ❌ 不做实体树可视化重做（`tree_builder` 降级即可）。
- ❌ 不做记忆衰减/遗忘（企业记忆不该遗忘，`decay.py` 保留但默认不进推理路径）。
- ❌ 不做跨租户共享记忆（安全边界，超出本期）。

---

## 附录：执行前自检清单

- [ ] 已 `cp tars.db tars.db.bak.*` 备份
- [ ] 已 `grep` 确认 `Database` 的 execute/fetch_all/fetch_one 实际方法名
- [ ] 已确认当前在新分支（建议 `feat/v4.4.0-portlogistics-orchestration`）
- [ ] 每个 Phase 做完跑一次后端冒烟（发一条消息能正常回）
- [ ] 全程不碰 `agent.py` / `main.py` 的硬拆分（那是 v4.3.3 已 defer 的独立重构）
