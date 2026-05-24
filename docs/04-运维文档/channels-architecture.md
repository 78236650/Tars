# TARS Channels 架构（v4.3.0）

> OpenClaw Phase 3 — ChannelRouter + WebSocket 一等实现

## 概述

v4.3.0 将 WebSocket 出站消息统一经 **ChannelRouter** 路由，为后续 IM / Webhook 通道预留 adapter 接口，而不改变 Chat 主流程语义。

## 组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `Channel` / `ChannelMessage` | `backend/tars/channels/base.py` | 通道抽象 |
| `WebSocketChannel` | `backend/tars/channels/websocket.py` | WS 入站解析 + 出站投递 |
| `ConnectionManager` | 同上 | 连接 ↔ session 映射 |
| `ChannelAdapter` | `backend/tars/channels/adapter.py` | 出站 adapter 协议 |
| `ChannelRouter` | `backend/tars/channels/router.py` | 注册 adapter、`send` / `stream` |
| `ChannelRegistry` | `backend/tars/channels/registry.py` | 读取 `channels.yaml` |
| 配置 | `backend/config/channels.yaml` | 特性开关与 adapter 列表 |

## 数据流

```
Agent / Cron / ApprovalService
        │
        ▼
ConnectionManager.send_personal_message (use_router=true)
        │
        ▼
ChannelRouter.send("websocket", session_id, event)
        │
        ▼
ConnectionManagerOutboundAdapter.deliver_outbound
        │
        ▼
WebSocketChannel._send_direct → 客户端
```

入站：`/ws` → `ChannelRouter.handle_websocket` → `WebSocketChannel.handle_message` → `AgentV2.handle_message`

## 配置

`backend/config/channels.yaml`：

```yaml
channels:
  use_router: true   # false 时 WebSocketChannel 直写 socket（兼容路径）
  adapters:
    websocket:
      enabled: true
      capabilities:
        - streaming
        - attachments
        - feedback
```

启动日志：`[Startup] ChannelRegistry loaded (use_router=true)`

## 相关 WS 事件（Phase 3）

| 事件 | 方向 | 说明 |
|------|------|------|
| `approval_required` | 服务端 → 客户端 | 高危工具待审批 |
| `approval_resolved` | 服务端 → 客户端 | 审批结果 |
| `subagent_handoff` | 服务端 → 客户端 | 子代理 `pending_review` / `accepted` / `rejected` |
| `subagent_handoff_action` | 客户端 → 服务端 | `{ action: accept\|reject, handoff_id }` |
| `cron_delegate_result` | 服务端 → 客户端 | Cron delegate 完成 |
| `cron_prompt_complete` | 服务端 → 客户端 | Cron prompt 一轮 Agent 结束 |

## 工具审批

- 策略：`backend/config/execution_policy.yaml`
- 服务：`backend/tars/security/approval_service.py`
- API：`POST /api/approvals/{id}/approve|deny`
- 前端：`frontend/src/components/chat/ApprovalDialog.vue`

## 子代理 Handoff

- 协议：`backend/tars/agent/handoff.py`
- API：`POST /api/handoffs/{id}/accept|reject`
- 前端：`frontend/src/components/chat/HandoffDialog.vue`
- `/subagent` 斜杠命令完成后 emit `subagent_handoff`（`pending_review`），accept 后才写入 assistant 消息

## 出站迁移残留（F-12，目标 v4.4）

`use_router=true` 时，`ConnectionManager.send_personal_message` 已内部转发至 `ChannelRouter.send("websocket", …)`。以下模块仍**直接调用** `connection_manager`，尚未改为显式 `channel_router.send`：

| 位置 | 说明 |
|------|------|
| `backend/tars/agent/agent.py` | handoff accept/reject 投递 |
| `backend/tars/cron/runtime.py` | `deliver_event` |
| `backend/tars/cron/executors/prompt.py` | prompt cron 事件 |
| `backend/tars/security/approval_service.py` | approval WS 事件 |

v4.4 目标：上述调用点归零，统一注入 `ChannelRouter`。

## 验证

```bash
cd backend
python3 -m pytest tests/test_channel_router.py tests/test_tool_approval.py \
  tests/test_cron_delegate_prompt.py tests/test_subagent_handoff.py -q
```

完整 Phase 3 验收脚本：

```bash
./scripts/acceptance/phase3-openclaw.sh
```

## 相关文档

- 设计：[openclaw-phase3-design.md](../superpowers/specs/2026-05-24-openclaw-phase3-design.md)
- 计划：[openclaw-phase3-plan.md](../superpowers/plans/2026-05-24-openclaw-phase3-plan.md)
- Cron：[CRONJOB_GUIDE.md](../../CRONJOB_GUIDE.md)
