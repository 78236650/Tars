# TARS v4.3.0 Phase 3: Channels & Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v4.3.0 OpenClaw-aligned execution layer — ChannelRouter (WebSocket PoC), full Cron types, tool approval, subagent handoff review.

**Architecture:** ChannelRouter → WebSocketChannel; CronTaskExecutor registry; ApprovalService in ToolDispatcher; SubagentHandoff protocol.

**Tech Stack:** Python 3.11 / FastAPI / Vue 3 / pytest

**Spec:** [2026-05-24-openclaw-phase3-design.md](../specs/2026-05-24-openclaw-phase3-design.md)

**Branch:** Create `v4.3.0` from merged `v4.2.0`. Do not start on `v4.2.0` branch until v4.2.0 release complete.

---

## File Map

| File | Action |
|------|--------|
| `backend/tars/channels/router.py` | Create |
| `backend/tars/channels/registry.py` | Create |
| `backend/tars/channels/adapter.py` | Create |
| `backend/tars/channels/websocket.py` | Modify — implement Channel fully |
| `backend/config/channels.yaml` | Create |
| `backend/tars/cron/executors/` | Create — reminder, delegate, prompt |
| `backend/tars/cron/runtime.py` | Modify — executor registry |
| `backend/tars/security/approval_service.py` | Create |
| `backend/tars/security/execution_policy.py` | Create |
| `backend/config/execution_policy.yaml` | Create |
| `backend/tars/api/approvals.py` | Create |
| `backend/tars/agent/handoff.py` | Create |
| `backend/tars/agent/follow_up_queue.py` | Create (stretch) |
| `backend/tars/main.py` | Modify — WS via ChannelRouter |
| `frontend/src/components/chat/ApprovalDialog.vue` | Create |
| `backend/tests/test_channel_router.py` | Create |
| `backend/tests/test_cron_delegate_prompt.py` | Create |
| `backend/tests/test_tool_approval.py` | Create |
| `backend/tests/test_subagent_handoff.py` | Create |
| `CRONJOB_GUIDE.md` | Update |

---

### Task 1: ChannelRouter + registry

**Files:**
- Create: `backend/tars/channels/router.py`, `registry.py`, `adapter.py`
- Create: `backend/config/channels.yaml`
- Test: `backend/tests/test_channel_router.py`

- [ ] **Step 1: Write failing test — register websocket adapter, send event to session**

```python
@pytest.mark.asyncio
async def test_router_send_routes_to_registered_channel():
    router = ChannelRouter()
    mock = AsyncMock()
    router.register("websocket", mock)
    await router.send("websocket", "sess-1", {"type": "token", "content": "hi"})
    mock.deliver_outbound.assert_called_once()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement ChannelRouter.register/send/stream**

- [ ] **Step 4: Load `config/channels.yaml` in startup**

- [ ] **Step 5: Run — expect PASS**

- [ ] **Step 6: Commit**

---

### Task 2: Refactor main.py WebSocket through router

**Files:**
- Modify: `backend/tars/main.py`
- Modify: `backend/tars/channels/websocket.py`

- [ ] **Step 1: Add feature flag `channels.use_router: true` in channels.yaml**

- [ ] **Step 2: `/ws` handler calls `ChannelRouter.handle_websocket(websocket, ...)`**

- [ ] **Step 3: Regression — existing WS integration test or manual chat stream**

- [ ] **Step 4: Commit**

---

### Task 3: Cron delegate + prompt executors

**Files:**
- Create: `backend/tars/cron/executors/base.py`, `reminder.py`, `delegate.py`, `prompt.py`
- Modify: `backend/tars/cron/runtime.py`
- Test: `backend/tests/test_cron_delegate_prompt.py`

- [ ] **Step 1: Test delegate executor invokes SubAgentManager and emits event**

- [ ] **Step 2: Test prompt executor runs one agent turn on session_id**

- [ ] **Step 3: Replace `print 未实现` branch with executor registry lookup**

- [ ] **Step 4: Audit log `cron_execute`**

- [ ] **Step 5: Commit**

---

### Task 4: ApprovalService + API

**Files:**
- Create: `backend/tars/security/approval_service.py`, `execution_policy.py`
- Create: `backend/tars/api/approvals.py`
- Create: `backend/config/execution_policy.yaml`
- Modify: `backend/tars/tools/dispatcher.py`
- Test: `backend/tests/test_tool_approval.py`

- [ ] **Step 1: Test shell tool creates pending approval, blocks until approved**

- [ ] **Step 2: Add `approval_requests` table**

- [ ] **Step 3: `POST /api/approvals/{id}/approve` and `/deny`**

- [ ] **Step 4: ToolDispatcher — await approval with 300s timeout**

- [ ] **Step 5: WS events `approval_required`, `approval_resolved`**

- [ ] **Step 6: Commit**

---

### Task 5: ApprovalDialog frontend

**Files:**
- Create: `frontend/src/components/chat/ApprovalDialog.vue`
- Modify: `frontend/src/stores/wsStore.ts` or chat handler

- [ ] **Step 1: Listen `approval_required`, show dialog with tool name + args summary**

- [ ] **Step 2: Approve/Deny calls API**

- [ ] **Step 3: Commit**

---

### Task 6: Subagent handoff protocol

**Files:**
- Create: `backend/tars/agent/handoff.py`
- Modify: `backend/tars/agent/subagent_manager.py`, `agent.py`
- Test: `backend/tests/test_subagent_handoff.py`

- [ ] **Step 1: Test delegate completion emits `subagent_handoff` pending_review**

- [ ] **Step 2: Accept API or WS action sets accepted, merges result**

- [ ] **Step 3: Parent prompt rule for verify-before-done**

- [ ] **Step 4: Commit**

---

### Task 7: Docs + integration tests

**Files:**
- Update: `CRONJOB_GUIDE.md`
- Create: `docs/04-运维文档/channels-architecture.md` (brief)

- [ ] **Step 1: Document delegate/prompt cron examples**

- [ ] **Step 2: Full regression checklist from spec §7.1**

- [ ] **Step 3: Commit**

---

### Task 8 (Stretch): Follow-up Queue

**Files:**
- Create: `backend/tars/agent/follow_up_queue.py`
- Test: `backend/tests/test_follow_up_queue.py`

- [ ] **Step 1: Enqueue message while agent busy**

- [ ] **Step 2: Drain after turn complete**

- [ ] **Step 3: WS `queue_status`**

- [ ] **Step 4: Commit**

---

## Spec Coverage

| MVP item | Task |
|----------|------|
| Channel architecture | 1, 2 |
| Cron full types | 3 |
| Tool approval | 4, 5 |
| Subagent handoff | 6 |
| Follow-up queue | 8 |

---

## Execution Handoff

**10–12 person-days**, 7–8 tasks. **Start only after v4.2.0 branch merges.**

Create branch: `git checkout -b v4.3.0 v4.2.0`
