# Phase 3：对标 OpenClaw — Channels & Execution 设计说明

> **文档日期**: 2026-05-24  
> **状态**: ✅ 已批准（2026-05-24）  
> **目标版本**: TARS **v4.3.0** "Channels & Execution"  
> **基座**: v4.2.0 合并后切分支 `v4.3.0`  
> **对标**: OpenClaw 2026.5.x（架构对齐 + 能力裁剪，非全量复刻）

---

## 一、目标与范围

### 1.1 战略选择（已确认）

| 维度 | 决策 |
|------|------|
| 对标方向 | **B** 执行与自动化 + **D** 架构对齐 |
| 通道 PoC | **D** — 不接入真实 IM；重构 WebSocket 为 Channel 实现 + adapter 接口 |
| 版本 | **v4.3.0** 独立分支（不挤占 v4.2.0） |

### 1.2 Phase 3 MVP（必做）

| # | 能力 | 说明 |
|---|------|------|
| 1 | **Channel 架构** | `ChannelRouter` + `ChannelAdapter` 注册；`WebSocketChannel` 为一等实现 |
| 2 | **Cron 全类型** | 实现 `delegate` + `prompt`（现有仅 `reminder`） |
| 3 | **工具执行审批** | shell/file_write 等高危工具 UI/API 确认；预留 `/approve` |
| 4 | **Subagent handoff 审查** | 子代理完成 → `pending_review` → 父 Agent 必须 verify |

### 1.3 Stretch（有余力）

| # | 能力 | 说明 |
|---|------|------|
| 5 | **轻量 Follow-up Queue** | Agent 运行中用户新消息入队，当前 turn 结束后处理（非 OpenClaw 全套 collect 模式） |

### 1.4 Out of Scope（v4.4+ 或不做）

- 飞书 / Slack / Telegram 实接
- 语音 / Discord voice
- Tauri 桌面客户端
- Codex harness / 平台级 Playwright Tool
- OpenClaw Policy 插件完整移植（仅借鉴 `ExecutionPolicy` 概念）

---

## 二、架构方案（选定：方案 2）

### 方案 1：散点补丁

- `CronRuntime` 加两个 elif
- ToolDispatcher 前加 if confirm
- 缺点：无法扩展 IM，审批与 Channel 脱节

### 方案 2：Channels + Execution 分层（推荐）

```
                    ChannelRouter
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
 WebSocketChannel    (future Feishu)    (future Webhook)
        │
        ▼
    Gateway → AgentV2 ← FollowUpQueue (stretch)
        │
        ├─ ToolDispatcher ← ApprovalService
        ├─ SubAgentManager ← HandoffProtocol
        └─ CronRuntime ← CronTaskExecutor registry
```

### 方案 3：OpenClaw 全量移植

- 过重，依赖 TS 生态与 Codex；**不采用**

---

## 三、组件设计

### 3.1 Channel 层（D）

**现有：** `channels/base.py` 已有 `Channel` / `ChannelMessage`；`websocket.py` 有实现。

**新增：**

| 组件 | 路径 | 职责 |
|------|------|------|
| `ChannelAdapter` | `channels/adapter.py` | 插件元数据：id, capabilities, inbound/outbound |
| `ChannelRouter` | `channels/router.py` | 注册 adapter、route send/stream、统一 session 映射 |
| `ChannelRegistry` | `channels/registry.py` | 配置驱动 `config/channels.yaml` |

**重构：**

- `main.py` `/ws` handler → 仅调用 `ChannelRouter.handle_connection(WebSocketChannel, ...)`
- 所有 outbound 事件经 `channel.send(session_id, event)`，禁止 scattered `connection_manager` 直调（渐进迁移）

**PoC 验收：**

- 现有 Chat 功能零回归（流式、附件、 insight strip）
- 单元测试：`WebSocketChannel` 实现 `Channel` 接口；`ChannelRouter` 路由 mock adapter

**Adapter 接口（预留，Phase 3 不实现）：**

```python
class ChannelAdapter(Protocol):
    channel_id: str
    async def connect(self, config: dict) -> None: ...
    async def normalize_inbound(self, raw: Any) -> ChannelMessage: ...
    async def deliver_outbound(self, session_id: str, event: dict) -> None: ...
```

### 3.2 Cron 全类型（A）

**现状：** `cron/runtime.py:57` — 非 reminder 打印「未实现」。

**新增 `CronTaskExecutor` 注册表：**

| task_type | Executor | 行为 |
|-----------|----------|------|
| `reminder` | `ReminderExecutor` | 现有逻辑 |
| `delegate` | `DelegateExecutor` | 调 `SubAgentManager.delegate_task()`，结果 WS 推送 |
| `prompt` | `PromptExecutor` | 对 `task_config.session_id` 注入 system+user prompt，跑一轮 Agent |

**task_config  schema：**

```json
// delegate
{"subagent_type": "code", "task": "review sql", "session_id": "..."}
// prompt
{"prompt": "总结今日待办", "session_id": "...", "model": "optional"}
```

**DB/API：** 现有 `/api/cronjobs` 不变；前端 Cron 创建 UI 增加类型选择（若已有表单则扩展）。

**审计：** `audit_logger` 记 `cron_execute` + task_type + job_id。

### 3.3 工具执行审批（C）

**新增：**

| 组件 | 路径 |
|------|------|
| `ApprovalService` | `security/approval_service.py` |
| `approval_requests` 表 | SQLite |
| API | `POST /api/approvals/{id}/approve|deny` |
| WS 事件 | `approval_required`, `approval_resolved` |

**流程：**

```
ToolDispatcher.execute_tool(name, args)
  → ExecutionPolicy.requires_approval(name, args, user_role)?
       yes → 创建 ApprovalRequest(pending) → WS approval_required → 阻塞等待（asyncio.Event, timeout 5min）
       user approve → 继续执行
       deny/timeout → ToolResult(error="denied")
```

**默认需审批工具：** `shell`, `command`, `file_write`, `python_exec`（可 `config/execution_policy.yaml` 覆盖）

**前端：**

- Chat 内 `ApprovalDialog` 展示命令摘要 + Approve/Deny
- 预留 `channel_id` 字段，v4.4 IM 按钮复用同一 `ApprovalService`

**与 OpenClaw 对齐点：** 单一 `/approve` 语义；Phase 3 仅 Web UI。

### 3.4 Subagent Handoff 审查（E）

**协议扩展（WS + 内部）：**

```python
@dataclass
class SubagentHandoff:
    status: Literal["running", "pending_review", "accepted", "rejected"]
    subagent_type: str
    task_summary: str
    result_preview: str
    parent_session_id: str
```

**行为变更：**

1. 子代理 `invoke` 完成 →  emit `subagent_handoff`（status=`pending_review`），**不**直接 merge 进父会话为 final
2. 父 Agent system prompt 增加规则：「收到 pending_review 必须先 summarize + 向用户确认或调用 `verify_subagent_result`」
3. 用户或父 Agent 调用 accept → status=`accepted`，结果写入会话
4. reject → 可选 re-delegate

**OpenClaw 对齐：** 2026.5.x「ready for parent review」语义。

### 3.5 Follow-up Queue（Stretch）

**`agent/follow_up_queue.py`：**

- Agent loop `running` 时新 user message → enqueue
- 当前 turn 完成后 drain queue（FIFO，合并同 session）
- WS 推送 `queue_status: {pending: N}`

**不做：** OpenClaw mid-turn interrupt / collect 模式 / steering 全量。

---

## 四、配置

**`backend/config/channels.yaml`**

```yaml
channels:
  websocket:
    enabled: true
    adapter: builtin.websocket
  # feishu:
  #   enabled: false
  #   adapter: plugins.feishu
```

**`backend/config/execution_policy.yaml`**

```yaml
approval:
  enabled: true
  timeout_seconds: 300
  require_for_tools: [shell, command, file_write, python_exec]
  auto_allow_for_roles: [admin]  # 可选
```

---

## 五、数据流

### Cron delegate

```
Scheduler trigger → CronRuntime.execute_job
  → DelegateExecutor → SubAgentManager.delegate(type, task)
  → ChannelRouter.send(session, {type: "cron_delegate_result", ...})
```

### Tool approval

```
LLM tool_call shell → ApprovalService.create
  → WS approval_required → User Approve
  → ToolDispatcher.execute (actual shell)
  → WS tool_result
```

### Subagent handoff

```
Parent delegates → Subagent runs → pending_review event
  → Parent turn continues with review instruction
  → accept/reject → session update
```

---

## 六、错误处理

| 场景 | 行为 |
|------|------|
| Approval 超时 | deny + audit |
| Cron delegate 子代理失败 | job last_run 仍更新；WS error event |
| ChannelRouter 无 session | log + drop outbound |
| prompt cron 无 session_id | job 标记 failed，不 crash scheduler |

---

## 七、测试与验收

### 7.1 必做验收

| # | 项 |
|---|-----|
| 1 | Chat WebSocket 回归：流式、工具、Insight strip 无破坏 |
| 2 | `delegate` cron 触发子代理并 WS 推送结果 |
| 3 | `prompt` cron 对指定 session 完成一轮 Agent |
| 4 | shell 调用弹出审批；deny 不执行；approve 后执行 |
| 5 | 子代理完成出现 pending_review；accept 后结果入会话 |
| 6 | `ChannelRouter` + `WebSocketChannel` 单元测试 ≥5 cases |
| 7 | Cron + Approval 集成测试；evolution 无关 |

### 7.2 Stretch 验收

| # | 项 |
|---|-----|
| 8 | Agent 运行中第二条消息排队，turn 结束后自动处理 |

### 7.3 测试文件

- `test_channel_router.py`
- `test_cron_delegate_prompt.py`
- `test_tool_approval.py`
- `test_subagent_handoff.py`
- `test_follow_up_queue.py`（stretch）

---

## 八、实施顺序（v4.3.0，约 10–12 人日）

| W | 工作包 | 人日 |
|---|--------|------|
| W1 | ChannelRouter + WebSocket  refactor | 2 |
| W2 | CronTaskExecutor delegate + prompt | 2 |
| W3 | ApprovalService + API + Chat UI | 2.5 |
| W4 | Subagent handoff 协议 + Agent 集成 | 2 |
| W5 | execution_policy.yaml + 文档 | 0.5 |
| W6 | 测试 + CRONJOB_GUIDE 更新 | 1.5 |
| W7 | Follow-up Queue（stretch） | 1.5 |

**分支策略：** `v4.2.0` 合并/main 稳定后，从 `v4.2.0` 切 `v4.3.0`。

---

## 九、风险

| 风险 | 缓解 |
|------|------|
| Channel 重构破坏 WS | 特性开关 `channels.use_router` 默认 true；保留旧路径 1 版本 |
| Approval 阻塞 Agent 过久 | 5min timeout + cancel turn |
| Subagent 审查增加延迟 | 仅 delegate 路径启用，普通工具不受影响 |
| v4.2.0 未合并就开 v4.3.0 | 明确依赖：Phase 3 开发在 v4.2.0 完成后启动 |

---

## 十、与 OpenClaw 对照（Phase 3 后预期）

| OpenClaw 能力 | v4.3.0 状态 |
|---------------|-------------|
| 多 Channel | 架构 ✅ / IM ❌ |
| Cron 全类型 | ✅ |
| Tool approval | ✅ Web |
| Subagent review handoff | ✅ |
| Queue steering | ⚠️ 轻量 queue |
| Browser/Codex/Voice | ❌ v4.4+ |

---

*评审通过后写入 implementation plan；随后 Phase 4（Dify 企业采购）头脑风暴。*
