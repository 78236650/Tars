# PortMeta Agent 工作流可视化编辑器 — 开发设计

> 日期：2026-05-30  
> 版本：v4.4.0 设计草案  
> 状态：待评审

---

## 一、能做什么（能力边界）

### 1.1 确定的交付物

| 层 | 内容 | 说明 |
|------|------|------|
| **前端** | DAG 画布 + 节点库 + 执行监控面板 | Vue 3 + 自绘 SVG/Canvas |
| **后端** | 工作流 CRUD API + 执行引擎 | FastAPI + 复用现有 PDCA |
| **集成** | 连接现有 Agent / Tool / Skill / 审批 | 零新依赖模块 |
| **模板** | 5 个内置工作流模板 | 代码审查 / 日报生成 / SQL 问答 / 部署 / 自定义 |

### 1.2 不做什么

- ❌ 不做低代码平台（不画 UI、不接 API 市场）
- ❌ 不做 Node-RED 级别通用流程引擎
- ❌ 不做跨项目工作流（单租户内闭环）
- ❌ 不做 Webhook 触发器（Phase 2）

---

## 二、节点类型

### 2.1 节点一览

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  LLM     │   │  Tool    │   │  Condition│   │  Approval │   │  Output  │
│  提示词   │   │  工具调用 │   │  条件分支  │   │  人工审批  │   │  结果输出 │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

| 节点 | 输入 | 输出 | 复用现有 |
|------|------|------|----------|
| **LLM** | System prompt + User prompt（支持 `{{变量}}`） | 文本 / JSON | AgentV2 单轮调用 |
| **Tool** | 工具名 + 参数 JSON | 执行结果 | ToolRegistry 全部 33 个工具 |
| **Condition** | 表达式（如 `$result.exit_code == 0`） | true / false 分支 | Python eval 沙箱 |
| **Approval** | 标题 + 描述 + 超时 | 通过 / 拒绝 / 超时自动通过 | ApprovalService（已有） |
| **Output** | Markdown 模板 | 格式化结果推送给用户 | 流式输出 Channel |

### 2.2 变量系统

工作流内节点间通过 `$node_id.field` 传递数据：

```json
{
  "node_id": "search_1",
  "tool": "web_search",
  "params": { "query": "$llm_1.result.summary" }
}
```

支持的变量路径：
- `$llm_1.result` — LLM 节点完整输出
- `$tool_1.exit_code` — 工具退出码
- `$tool_1.stdout` — 工具标准输出
- `$trigger.user_message` — 触发工作流的用户消息
- `$trigger.session_id` — 当前会话 ID

---

## 三、画布交互设计

### 3.1 布局

```
┌──────────────────────────────────────────────────────┐
│  工作流名称  [保存] [运行] [导出]      模板库 ▼      │
├────────────┬─────────────────────────────────────────┤
│  节点面板   │                                         │
│            │        ┌─────┐     ┌──────┐             │
│  💬 LLM    │   Start─┤ LLM ├─────┤ Tool ├──┐         │
│            │        └─────┘     └──────┘  │         │
│  🔧 Tool   │                              ▼         │
│            │                    ┌──────────────┐    │
│  🔀 条件   │                    │  Condition   │    │
│            │                    └──┬────────┬──┘    │
│  ✋ 审批   │                   ✅true  ❌false       │
│            │                    │          │         │
│  📤 输出   │                    ▼          ▼         │
│            │              ┌────────┐  ┌────────┐    │
│            │              │ Output │  │  LLM   │    │
│            │              └────────┘  └────────┘    │
├────────────┴─────────────────────────────────────────┤
│  执行日志：Step 1/4 ✓ web_search 完成 (1.2s)       │
└──────────────────────────────────────────────────────┘
```

### 3.2 操作方式

| 操作 | 交互 |
|------|------|
| 拖入节点 | 从左侧面板拖到画布 |
| 连线 | 从节点输出点拖到目标节点输入点 |
| 编辑节点 | 双击弹出属性面板 |
| 删除节点/线 | 选中按 Delete |
| 运行 | 点击「运行」→ 节点依次变色（灰→蓝→绿/红） |
| 暂停/继续 | 审批节点处暂停，用户操作后继续 |

---

## 四、数据模型

### 4.1 工作流定义（JSON）

```json
{
  "id": "wf_abc123",
  "tenant_id": "default",
  "name": "每日代码审查",
  "description": "拉取最新 commit 并生成审查报告",
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "position": { "x": 100, "y": 200 }
    },
    {
      "id": "git_log",
      "type": "tool",
      "tool_name": "shell",
      "params": { "command": "git log --oneline -5" },
      "position": { "x": 300, "y": 200 }
    },
    {
      "id": "llm_review",
      "type": "llm",
      "system_prompt": "你是代码审查专家",
      "user_prompt": "审查以下 commit：\n{{$git_log.stdout}}",
      "position": { "x": 500, "y": 200 }
    },
    {
      "id": "output",
      "type": "output",
      "template": "## 审查报告\n\n{{$llm_review.result}}",
      "position": { "x": 700, "y": 200 }
    }
  ],
  "edges": [
    { "from": "start", "to": "git_log" },
    { "from": "git_log", "to": "llm_review" },
    { "from": "llm_review", "to": "output" }
  ],
  "created_at": "2026-05-30T...",
  "updated_at": "2026-05-30T..."
}
```

### 4.2 执行状态

```json
{
  "run_id": "run_xyz",
  "workflow_id": "wf_abc123",
  "status": "running",
  "current_node": "llm_review",
  "nodes": {
    "start": "completed",
    "git_log": "completed",
    "llm_review": "running",
    "output": "pending"
  },
  "outputs": {
    "git_log": { "exit_code": 0, "stdout": "abc123\n..." }
  },
  "started_at": "...",
  "steps_completed": 2,
  "steps_total": 4
}
```

### 4.3 数据库表

```sql
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    definition TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    state TEXT NOT NULL DEFAULT '{}',  -- JSON: 执行状态快照
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
```

---

## 五、后端执行引擎

### 5.1 架构

```
WorkflowExecutor
  ├── NodeExecutor (按拓扑排序执行)
  │   ├── LLMNodeExecutor   → AgentV2 单轮
  │   ├── ToolNodeExecutor  → ToolDispatcher
  │   ├── ConditionNodeExecutor → Python eval
  │   ├── ApprovalNodeExecutor   → ApprovalService
  │   └── OutputNodeExecutor     → Channel.send
  ├── VariableResolver (解析 $node.field)
  └── RunStateStore (WebSocket 实时推送状态)
```

### 5.2 执行流程

```
1. 解析 DAG → 拓扑排序 → 执行队列
2. 逐节点执行：
   a. 解析输入变量（$node.field → 实际值）
   b. 调用对应 Executor
   c. 存储输出到 run state
   d. WebSocket 推送节点状态变更
3. 条件分支：根据 true/false 跳转
4. 审批：暂停执行 → 用户操作 → 恢复
5. 全部完成 → 输出节点结果推送到会话
```

### 5.3 复用清单

| 能力 | 来源 | 改动 |
|------|------|------|
| LLM 调用 | `AgentV2` | 封装单轮调用方法 |
| 工具执行 | `ToolDispatcher` | 直接复用 |
| 审批 | `ApprovalService` | 直接复用 |
| 输出推送 | `Channel.send` | 直接复用 |
| 变量引擎 | `orchestration/variable_engine.py` | 扩展 `$node.field` 语法 |
| 验证 | `orchestration/verifier.py` | 直接复用 |
| PDCA | `orchestration/` 全套 | 替代为 DAG 驱动 |

---

## 六、内置模板

| 模板 | 节点链 | 场景 |
|------|--------|------|
| **代码审查** | Shell(git log) → LLM(审查) → Output | 日常开发 |
| **日报生成** | Shell(今日提交) + BI(数据查询) → LLM(汇总) → Output | 管理 |
| **SQL 问答** | LLM(生成 SQL) → Tool(bi_query) → Condition(检查结果) → LLM(解读) → Output | 数据分析 |
| **智能部署** | Shell(build) → Condition(exit code) → Approval → Shell(deploy) → Output | DevOps |
| **空白工作流** | Start → (用户自由搭建) → Output | 通用 |

---

## 七、前端技术选型

### 7.1 流程图渲染

两个方案：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **自绘 SVG** | 零依赖，完全可控 | 开发量 ~2 周 |
| **Vue Flow** | 成熟库，社区 20k+ star | 引入 200KB 依赖 |

**推荐 Vue Flow** — 已经有拖拽、连线、缩放、小地图等基础能力，只需定制节点 UI 和执行动画。

### 7.2 技术栈

```
前端：Vue 3 + Vue Flow + Tailwind
后端：FastAPI + SQLite (复用现有)
通信：WebSocket (复用现有 Channel)
```

---

## 八、分阶段实施

### Phase 1：核心画布 + LLM/Tool 节点（1 周）

- [ ] Vue Flow 集成 + 节点渲染
- [ ] LLM 节点 + Tool 节点
- [ ] 变量解析 `$node.field`
- [ ] 后端工作流 CRUD API
- [ ] 后端执行引擎（线性，无条件分支）
- [ ] WebSocket 实时状态推送
- [ ] 2 个模板：代码审查、SQL 问答

### Phase 2：条件 + 审批 + Output（1 周）

- [ ] Condition 节点
- [ ] Approval 节点
- [ ] DAG 拓扑排序（支持分支）
- [ ] Output 节点（Markdown 渲染）
- [ ] 执行动画（节点变色）
- [ ] 模板市场页面

### Phase 3：模板系统 + 触发（1 周）

- [ ] 模板导入/导出 JSON
- [ ] 从对话中一键生成工作流（Agent 反转）
- [ ] Cron 定时触发工作流
- [ ] 工作流运行历史 + 回放

---

## 九、与竞品对比

| 能力 | PortMeta v4.4 | Dify | Coze |
|------|:---:|:---:|:---:|
| 可视化工作流 | ✅ | ✅ | ✅ |
| 私有化部署 | ✅ | ✅ | ❌ |
| 多租户 | ✅ | ✅ | ❌ |
| 审批节点 | ✅ | ❌ | ❌ |
| 记忆系统集成 | ✅ | ❌ | ❌ |
| 知识库 RAG 集成 | ✅ | ✅ | ✅ |
| 模板市场 | ✅ Phase 3 | ✅ | ✅ |
| 移动端 | ❌ | ❌ | ✅ |

---

## 十、能到什么地步 — 一句话总结

**不是再造一个 Dify，而是让 TARS 已有的 33 个工具 + 记忆 + 知识库，以可视化方式串成可复用、可审批、可监控的自动化流程。** 一个港口调度员可以在 10 分钟内拖出一个「每日船舶计划 + 堆场状态 + 天气预警 → 日报」的工作流，而不需要写一行代码。
