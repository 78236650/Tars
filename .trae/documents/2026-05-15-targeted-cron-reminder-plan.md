# 定向 Cron Reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 cron reminder 只投递到创建该提醒的会话，而不是广播给所有在线 WebSocket 连接。

**Architecture:** 保持现有 `cronjob -> Database -> CronRuntime -> WebSocket` 主链路不变，只补一层稳定的 `session_id` 路由。创建 reminder 时将会话标识写入 `task_config`，WebSocket 连接管理器维护 `session_id -> connection` 映射，`CronRuntime` 到点后优先按 `session_id` 精确发送，前端仅接收当前会话消息。

**Tech Stack:** Python 3 / FastAPI / WebSocket / SQLite / Vue 3 / Pinia / pytest

---

## Summary

本计划只实现“按会话定向提醒”，不扩展离线保留、多用户多窗口聚合或新的通知 UI。核心修复点有三个：

1. WebSocket 连接生命周期里显式绑定当前聊天 `session_id`
2. 创建 reminder 时把 `session_id` 写入 `task_config`
3. `CronRuntime` 从广播切到 `send_personal_message(session_id, event)` 精确发送

这能确保你在会话 A 创建的提醒，只在会话 A 到点收到，不会泄露到其他在线窗口。

## Current State Analysis

- `CronRuntime` 当前在 [runtime.py](file:///Users/daobanxiang/myproject/TARS/backend/tars/cron/runtime.py) 的 `_run_reminder()` 里无条件调用 `broadcast(event)`，即使 `task_config` 里已有 `session_id` 字段，也没有真正做定向路由。
- `ConnectionManager` 当前在 [websocket.py](file:///Users/daobanxiang/myproject/TARS/backend/tars/channels/websocket.py) 中把 `active_connections` 存成单层字典，键名虽然叫 `session_id`，但在 `main.py` 的 `_serve_websocket()` 里实际传入的是随机 `connection_id`，所以 `send_personal_message(session_id, ...)` 不能稳定命中真实聊天会话。
- `CronJobTool` 当前在 [cronjob.py](file:///Users/daobanxiang/myproject/TARS/backend/tars/tools/builtin/cronjob.py) 里只接受显式 `task_config`，不会自动注入当前聊天会话的 `session_id`。
- 前端 [ChatView.vue](file:///Users/daobanxiang/myproject/TARS/frontend/src/views/ChatView.vue) 已能显示 `cron_reminder`，但后端尚未保证事件只发到当前会话。

## Assumptions & Decisions

- 只以 `session_id` 为定向标识，不做 `user_id` 聚合。
- 如果 reminder 缺少 `session_id`，保持向后兼容：
  - 已存在老任务：允许 fallback 到广播或丢弃，但必须在代码中明确一种行为。
  - 推荐行为：记录警告并广播一次，仅用于兼容旧数据。
- 不修改 cronjobs 表结构，仍把 `session_id` 放在 `task_config` JSON 中。
- 不新增前端页面或通知中心，提醒仍显示为聊天系统消息。
- 必须先补测试再改实现，遵循 TDD。

## Proposed Changes

### Task 1: 锁定定向提醒的失败测试

**Files:**
- Modify: `backend/tests/unit/test_cron_runtime.py`
- Modify: `backend/tests/unit/test_tenant_websocket.py` 或新建 `backend/tests/unit/test_websocket_routing.py`

- [ ] **Step 1: 写 `CronRuntime` 定向发送失败测试**

```python
@pytest.mark.asyncio
async def test_cron_runtime_sends_reminder_to_session_only(tmp_path):
    from tars.cron.runtime import CronRuntime

    class FakeConnectionManager:
        def __init__(self):
            self.personal = []
            self.broadcasted = []

        async def send_personal_message(self, session_id, event):
            self.personal.append((session_id, event))

        async def broadcast(self, event):
            self.broadcasted.append(event)

    db = Database(db_path=str(tmp_path / "cron.db"))
    job = db.create_cronjob(
        user_id="default",
        name="会议提醒",
        cron_expression="5 14 * * *",
        task_type="reminder",
        task_config='{"message":"开会","session_id":"session-a"}',
    )
    cm = FakeConnectionManager()
    runtime = CronRuntime(db=db, scheduler=FakeScheduler(), connection_manager=cm)

    await runtime.execute_job(job.id)

    assert cm.personal and cm.personal[0][0] == "session-a"
    assert cm.broadcasted == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/unit/test_cron_runtime.py::test_cron_runtime_sends_reminder_to_session_only -q`

Expected: FAIL，因为当前实现仍调用 `broadcast()`。

- [ ] **Step 3: 写 WebSocket 路由失败测试**

```python
@pytest.mark.asyncio
async def test_connection_manager_can_route_by_session_id():
    manager = ConnectionManager()
    channel = FakeChannel()

    manager.bind_session("session-a", channel)
    await manager.send_personal_message("session-a", {"type": "cron_reminder"})

    assert channel.events == [{"type": "cron_reminder"}]
```

- [ ] **Step 4: 运行测试确认失败**

Run: `pytest backend/tests/unit/test_websocket_routing.py -q`

Expected: FAIL，因为当前 `ConnectionManager` 没有稳定的 `session_id -> channel` 绑定接口。

- [ ] **Step 5: 提交测试基线**

```bash
git add backend/tests/unit/test_cron_runtime.py backend/tests/unit/test_websocket_routing.py
git commit -m "test: cover targeted cron reminder routing"
```

### Task 2: 给 ConnectionManager 补稳定的 session 路由

**Files:**
- Modify: `backend/tars/channels/websocket.py`
- Modify: `backend/tars/main.py`
- Test: `backend/tests/unit/test_websocket_routing.py`

- [ ] **Step 1: 在 `ConnectionManager` 增加会话绑定接口**

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocketChannel] = {}
        self.session_connections: dict[str, str] = {}
        self.agent = None

    def bind_session(self, session_id: str, connection_id: str):
        if session_id:
            self.session_connections[session_id] = connection_id

    def unbind_session(self, session_id: str):
        self.session_connections.pop(session_id, None)
```

- [ ] **Step 2: 让 `send_personal_message()` 先按 `session_id` 找到 connection**

```python
async def send_personal_message(self, session_id: str, event: dict):
    connection_id = self.session_connections.get(session_id, session_id)
    if connection_id in self.active_connections:
        await self.active_connections[connection_id].send(session_id, event)
```

- [ ] **Step 3: 在 WebSocket 收到普通聊天消息后绑定 `session_id`**

```python
message = await self.receive(raw_message)
if websocket_manager is not None:
    websocket_manager.bind_session(message.session_id, self.connection_id)
```

说明：如果当前 `WebSocketChannel` 没有 `connection_id` 或 manager 引用，需要在构造函数中注入，避免靠全局变量。

- [ ] **Step 4: 在断连时清理关联的 `session_id`**

```python
def disconnect(self, connection_id: str):
    if connection_id in self.active_connections:
        del self.active_connections[connection_id]
    stale_sessions = [sid for sid, cid in self.session_connections.items() if cid == connection_id]
    for sid in stale_sessions:
        self.unbind_session(sid)
```

- [ ] **Step 5: 运行路由测试**

Run: `pytest backend/tests/unit/test_websocket_routing.py -q`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/tars/channels/websocket.py backend/tars/main.py backend/tests/unit/test_websocket_routing.py
git commit -m "feat: route websocket messages by session id"
```

### Task 3: 创建 reminder 时注入当前 session_id

**Files:**
- Modify: `backend/tars/tools/builtin/cronjob.py`
- Search: `backend/tars/agent/agent.py`
- Test: `backend/tests/unit/test_cron_runtime.py`

- [ ] **Step 1: 写失败测试，验证 tool 创建时会注入 `session_id`**

```python
@pytest.mark.asyncio
async def test_cronjob_tool_create_injects_session_id(tmp_path):
    db = Database(db_path=str(tmp_path / "cron.db"))
    tool = CronJobTool(db=db, cron_runtime=FakeRuntime())

    await tool.execute(
        action="create",
        name="提醒我",
        cron="5 14 * * *",
        task_type="reminder",
        task_config={"message": "到了"},
        session_id="session-a",
    )

    job = db.get_user_cronjobs("default")[0]
    config = json.loads(job.task_config)
    assert config["session_id"] == "session-a"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/unit/test_cron_runtime.py::test_cronjob_tool_create_injects_session_id -q`

Expected: FAIL，因为当前 tool 不会自动写入 `session_id`。

- [ ] **Step 3: 在 `CronJobTool._create()` 合并 `session_id`**

```python
task_config_dict = dict(args.get("task_config", {}))
if task_type == "reminder" and args.get("session_id") and "session_id" not in task_config_dict:
    task_config_dict["session_id"] = args["session_id"]
task_config = json.dumps(task_config_dict)
```

- [ ] **Step 4: 确认 Agent 调用 tool 时是否会传入 `session_id`**

如果当前 `ToolDispatcher` 或 `AgentV2` 没有把 `session_id` 透传给工具调用，需要在最小范围内补上；优先复用现有工具上下文，不做大重构。

- [ ] **Step 5: 运行测试**

Run: `pytest backend/tests/unit/test_cron_runtime.py -q`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/tars/tools/builtin/cronjob.py backend/tests/unit/test_cron_runtime.py
git commit -m "feat: inject session id into reminder cronjobs"
```

### Task 4: 将 CronRuntime 从广播改为定向发送

**Files:**
- Modify: `backend/tars/cron/runtime.py`
- Test: `backend/tests/unit/test_cron_runtime.py`

- [ ] **Step 1: 修改 `_run_reminder()` 优先按 `session_id` 精确投递**

```python
async def _run_reminder(self, job, config: dict[str, Any]) -> None:
    message = config.get("message") or job.description or job.name
    event = {
        "type": "cron_reminder",
        "job_id": job.id,
        "session_id": config.get("session_id", "default"),
        "message": message,
        "timestamp": _now_local().isoformat(),
    }
    session_id = config.get("session_id")
    if session_id:
        await self.connection_manager.send_personal_message(session_id, event)
    else:
        await self.connection_manager.broadcast(event)
```

- [ ] **Step 2: 对旧任务缺少 `session_id` 的行为写清楚**

推荐实现：

```python
if not session_id:
    print(f"[CronRuntime] reminder {job.id} 缺少 session_id，回退为 broadcast")
    await self.connection_manager.broadcast(event)
    return
```

- [ ] **Step 3: 运行定向提醒测试**

Run: `pytest backend/tests/unit/test_cron_runtime.py::test_cron_runtime_sends_reminder_to_session_only -q`

Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/tars/cron/runtime.py backend/tests/unit/test_cron_runtime.py
git commit -m "feat: send cron reminders to target session"
```

### Task 5: 校验前端仅在目标会话显示提醒

**Files:**
- Modify: `frontend/src/views/ChatView.vue`
- Optional Test: `frontend/src/views/__tests__/ChatView.*`（仅当项目已有前端测试基建可复用）

- [ ] **Step 1: 检查现有 `cron_reminder` 分支是否需要 session 过滤**

当前代码直接 push 系统消息：

```ts
} else if (data.type === 'cron_reminder') {
  messages.value.push({
    id: `${Date.now()}_cron_reminder`,
    role: 'system',
    content: `⏰ ${data.message}`,
    timestamp: data.timestamp
  })
}
```

若后端已做到“只投给目标会话”，前端可保持不变。  
若仍存在同一连接切换不同会话的场景，则补充：

```ts
if (chatStore.currentSessionId && data.session_id !== chatStore.currentSessionId) {
  return
}
```

- [ ] **Step 2: 本地手测**

手测步骤：
1. 打开会话 A，创建 1 分钟后的 reminder
2. 再打开会话 B
3. 到点后确认只有会话 A 收到 `⏰` 系统消息

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/ChatView.vue
git commit -m "fix: display cron reminders only in target session"
```

## Verification Steps

- 后端单测：
  - `pytest backend/tests/unit/test_cron_runtime.py -q`
  - `pytest backend/tests/unit/test_websocket_routing.py -q`
- 相关回归：
  - `pytest backend/tests/test_tools_skills.py -q`
  - 如 WebSocket 已有测试，可补跑相邻用例
- 手动验证：
  - 同浏览器两个不同会话页面同时在线
  - 在会话 A 创建 reminder
  - 到点仅 A 收到 `cron_reminder`
  - 删除/禁用任务后不再触发

## Spec Coverage Check

- 定向提醒：由 Task 2 + Task 4 实现
- reminder 创建时绑定当前会话：由 Task 3 实现
- 前端只在目标会话显示：由 Task 5 验证
- 启动加载与现有 scheduler 主链路：保持现有实现，不新增额外需求

## Risks & Failure Modes

- 如果 Agent 调用工具链没有透传 `session_id`，Task 3 需要在 `AgentV2` 或 `ToolDispatcher` 做最小补丁。
- 如果一个 WebSocket 连接在生命周期内频繁切换会话，`session_connections` 需要以“最后一次收到消息的 session”为准；这在单聊天页场景可接受。
- 旧 cronjob 数据缺少 `session_id` 时会回退广播；这是兼容行为，不视为新逻辑缺陷。
