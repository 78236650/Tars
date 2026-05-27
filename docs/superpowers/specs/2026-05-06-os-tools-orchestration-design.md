---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# OS 操作能力 + 多工具编排设计

## 概述

扩展 TARS Agent 的 OS 操作能力（文件写入、shell、进程、网络）并引入 Planner/Executor 模式的多工具编排机制。所有操作约束在 workspace 沙箱内。

## 核心设计

### 安全模型：Workspace 沙箱

- 所有文件操作限制在配置的 workspace 目录内
- 通过路径解析确保不逃逸（`../../etc` 被拒绝）
- 删除操作、超出 workspace 的操作需要用户确认

### 新增 OS 工具（4 个）

#### FileWriteTool
```python
name = "file_write"
parameters_schema = {
    "path": "文件路径（相对 workspace）",
    "content": "文件内容",
    "mode": "write / append / insert",
    "line": "insert 模式的行号"
}
```

#### ShellTool（替代 CommandTool）
- 黑名单模式：只禁止超高危（`rm -rf /`、fork bomb、`curl | sh` 等）
- 删除操作触发确认流程
- 未知/高危命令通过 WebSocket 发送 `confirmation_required` 事件

#### ProcessTool
```python
name = "process"
parameters_schema = {
    "action": "list / start / stop / status",
    "command": "start 时的命令",
    "pid": "stop 时的 PID",
    "name": "按名称过滤"
}
```

#### NetworkTool
```python
name = "network"
parameters_schema = {
    "action": "ping / port_check / http_test / dns_lookup",
    "host": "目标主机",
    "port": "端口号",
    "url": "HTTP 测试 URL"
}
```

### Planner/Executor 编排

**流程**：
```
用户请求 → LLM 判断复杂度
         ├─ 简单：直接 chat_with_tools
         └─ 复杂：调用 task_planner 工具提交计划
                 ↓
            TaskExecutor 按步骤执行
            每步推送 plan_step_* 事件
            失败自动重试（最多 2 次）
            失败后用户选择 skip / abort / retry
```

**TaskPlannerTool**（LLM 调用它来提交计划）：
```python
name = "task_planner"
parameters_schema = {
    "goal": "最终目标",
    "steps": [
        {
            "id": 1,
            "description": "步骤描述",
            "tool": "工具名",
            "arguments": {...},
            "depends_on": [0]
        }
    ]
}
```

**步骤间数据传递**：通过 `{{step_N.output}}` 占位符引用前序步骤的输出。

**TaskExecutor 逻辑**：
1. 按 id 顺序执行（depends_on 仅用于展示）
2. 每步前解析 `{{step_N.output}}` 占位符
3. 失败重试 2 次
4. 仍失败则发 `plan_step_failed` 等用户决策
5. 所有步骤完成后发 `plan_complete`

### WebSocket 新事件

| 事件 | 说明 |
|------|------|
| `plan_created` | 计划已生成 |
| `plan_step_start` | 某步开始 |
| `plan_step_complete` | 某步完成 |
| `plan_step_failed` | 失败等待决策 |
| `plan_step_retry` | 重试中 |
| `plan_complete` | 全部完成 |
| `confirmation_required` | 需用户确认（高危） |
| `user_decision` | 前端→后端，回传决策 |

## 文件变更

**新增**：
- `tars/tools/sandbox.py` — WorkspaceSandbox
- `tars/tools/builtin/file_write.py` — FileWriteTool
- `tars/tools/builtin/shell.py` — ShellTool
- `tars/tools/builtin/process.py` — ProcessTool
- `tars/tools/builtin/network.py` — NetworkTool
- `tars/orchestration/__init__.py`
- `tars/orchestration/models.py` — TaskPlan, TaskStep
- `tars/orchestration/planner.py` — TaskPlannerTool
- `tars/orchestration/executor.py` — TaskExecutor
- `frontend/src/components/chat/PlanCard.vue`
- `frontend/src/components/chat/ConfirmationDialog.vue`

**修改**：
- `tars/tools/builtin/__init__.py` — 导出新工具
- `tars/main.py` — 注册新工具 + 初始化 sandbox + executor
- `tars/agent/agent.py` — system prompt 加入 task_planner 指引
- `tars/channels/websocket.py` — 处理 user_decision 消息
- `frontend/src/views/ChatView.vue` — 处理 plan_* / confirmation 事件

**删除**：
- `tars/tools/builtin/command.py`（被 shell.py 替代）

## 前端 UI

**PlanCard**：进度式展示每步状态（✅/🔄/⬜）

**ConfirmationDialog**：高危操作弹窗（允许/拒绝）

**FailureDialog**：失败决策（重试/跳过/中止）

## 实现阶段

1. WorkspaceSandbox + FileWriteTool
2. ShellTool（替代 CommandTool）
3. ProcessTool + NetworkTool
4. orchestration 模块（Planner + Executor）
5. 前端 PlanCard + 确认弹窗 + 事件处理
6. 测试

## 测试计划

- **Sandbox**：路径逃逸拒绝、workspace 内允许
- **FileWriteTool**：write/append/insert 三种模式
- **ShellTool**：黑名单阻止、普通命令通过、删除触发确认
- **ProcessTool**：list / start / stop
- **NetworkTool**：端口测试、HTTP 测试
- **TaskPlanner**：LLM 提交计划后 TaskExecutor 能按序执行
- **Executor**：失败重试、占位符替换、用户决策分支
- 集成：完整端到端流程（创建项目脚手架）
