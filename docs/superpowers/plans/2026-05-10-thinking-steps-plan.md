---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 系统处理步骤显示实施计划（v2.6）

- **日期**：2026-05-10
- **版本**：v1.0
- **上游设计**：`2026-05-10-thinking-steps-design.md`
- **状态**：待实施

---

## 一、实施概览

### 1.1 改动范围

| 层级 | 文件 | 改动类型 |
|------|------|---------|
| 后端 | `backend/tars/agent/agent.py` | 修改 |
| 后端 | `backend/tars/tools/dispatcher.py` | 修改 |
| 前端 | `frontend/src/hooks/useWebSocket.ts` | 修改 |
| 前端 | `frontend/src/stores/wsStore.ts` | 修改 |
| 前端 | `frontend/src/components/chat/ChatPanel.vue` | 修改 |

### 1.2 实施顺序

1. **Phase 1**: 后端事件发送（agent.py + dispatcher.py）
2. **Phase 2**: 前端事件解析（useWebSocket.ts）
3. **Phase 3**: 前端状态管理（wsStore.ts）
4. **Phase 4**: 前端 UI 渲染（ChatPanel.vue）

---

## 二、Phase 1: 后端事件发送

### 2.1 agent.py 改动

**文件**：`backend/tars/agent/agent.py`

**改动点 1**：在 `handle_message` 方法开头发送 `thinking_start`

```python
# 在第 121 行 handle_message 入口
# 原代码后添加：
await channel.send(session_id, {
    "type": "thinking_start",
    "session_id": session_id,
    "timestamp": now_iso(),
})
```

**改动点 2**：在记忆检索前发送 `thinking_step`

```python
# 在 memory_router.retrieve() 调用前（约第 290 行）
if self.memory_router:
    await channel.send(session_id, {
        "type": "thinking_step",
        "step": "🧠",
        "title": "检索相关记忆",
        "detail": f"查询: {query[:30]}...",
        "session_id": session_id,
        "timestamp": now_iso(),
    })
```

**改动点 3**：在 chat_with_tools 调用前发送 `thinking_step`

```python
# 在 dispatcher.chat_with_tools 调用前（约第 365 行）
await channel.send(session_id, {
    "type": "thinking_step",
    "step": "💭",
    "title": "生成回答",
    "session_id": session_id,
    "timestamp": now_iso(),
})
```

**改动点 4**：在处理完成发送 `thinking_complete`

```python
# 在 full_response 收集完成后（约第 392 行后）
await channel.send(session_id, {
    "type": "thinking_complete",
    "session_id": session_id,
    "timestamp": now_iso(),
})
```

### 2.2 dispatcher.py 改动

**文件**：`backend/tars/tools/dispatcher.py`

**改动点**：在工具调用回调中发送 `thinking_step`

```python
# 在 chat_with_tools 方法中
# on_tool_call 回调添加：
async def on_tool_call(tool_name: str, arguments: dict):
    # 原有逻辑...
    # 新增：发送 thinking_step
    if on_tool_result:  # 通过 channel 发送需要回调
        pass  # 保持现状，通过 agent.py 的 on_tool_call 发送

# 推荐方案：在 agent.py 的 on_tool_call 回调中统一发送
# dispatcher.py 不需要改动
```

**说明**：工具调用的 `thinking_step` 通过 agent.py 中的 `on_tool_call` 回调发送，dispatcher.py 保持不变。

---

## 三、Phase 2: 前端事件解析

### 3.1 useWebSocket.ts 改动

**文件**：`frontend/src/hooks/useWebSocket.ts`

**改动点**：在 `onEvent` 回调中解析新事件

```typescript
// 在 ws.onmessage 回调中添加（约第 60 行）
ws.onmessage = (event) => {
  try {
    const data = JSON.parse(event.data)

    // 处理 thinking 事件
    if (data.type === 'thinking_start' || data.type === 'thinking_step' || data.type === 'thinking_complete') {
      onEvent?.(data)
      return
    }

    // ... 现有逻辑
  } catch (e) {
    console.error('[WebSocket] Parse error:', e)
  }
}
```

---

## 四、Phase 3: 前端状态管理

### 4.1 wsStore.ts 改动

**文件**：`frontend/src/stores/wsStore.ts`

**新增类型**：

```typescript
// 新增 ThinkingStep 和 ThinkingState 类型
export interface ThinkingStep {
  id: string
  step: string
  title: string
  detail?: string
  timestamp: string
}

export interface ThinkingState {
  isActive: boolean
  steps: ThinkingStep[]
}
```

**新增状态和方法**：

```typescript
// 在现有 store 中添加
const thinkingStates = ref<Record<string, ThinkingState>>({})

function handleThinkingStart(sessionId: string) {
  thinkingStates.value[sessionId] = {
    isActive: true,
    steps: []
  }
}

function handleThinkingStep(sessionId: string, data: any) {
  if (!thinkingStates.value[sessionId]) {
    thinkingStates.value[sessionId] = { isActive: true, steps: [] }
  }
  thinkingStates.value[sessionId].steps.push({
    id: `${Date.now()}-${Math.random()}`,
    step: data.step,
    title: data.title,
    detail: data.detail,
    timestamp: data.timestamp
  })
}

function handleThinkingComplete(sessionId: string) {
  if (thinkingStates.value[sessionId]) {
    thinkingStates.value[sessionId].isActive = false
  }
}

function getThinkingState(sessionId: string): ThinkingState | null {
  return thinkingStates.value[sessionId] || null
}

function clearThinkingState(sessionId: string) {
  delete thinkingStates.value[sessionId]
}
```

---

## 五、Phase 4: 前端 UI 渲染

### 5.1 ChatPanel.vue 改动

**文件**：`frontend/src/components/chat/ChatPanel.vue`

**改动点 1**：新增响应式变量

```typescript
// 在 script setup 中添加
const expandedThinking = ref<Set<string>>(new Set())

const toggleThinking = (msgId: string) => {
  if (expandedThinking.value.has(msgId)) {
    expandedThinking.value.delete(msgId)
  } else {
    expandedThinking.value.add(msgId)
  }
}

const isThinkingExpanded = (msgId: string) => expandedThinking.value.has(msgId)
```

**改动点 2**：在 assistant 消息模板中添加处理步骤区域

```vue
<!-- 在 assistant 消息气泡内，消息内容后添加 -->
<div v-if="m.thinking && m.thinking.steps.length > 0" class="mt-3">
  <div
    class="thinking-panel"
    @click="toggleThinking(m.id)"
  >
    <div class="thinking-header">
      <span>{{ isThinkingExpanded(m.id) ? '▼' : '▶' }}</span>
      <span>🔄 处理步骤</span>
      <span class="step-count">({{ m.thinking.steps.length }})</span>
    </div>

    <div v-if="isThinkingExpanded(m.id)" class="thinking-steps">
      <div
        v-for="step in m.thinking.steps"
        :key="step.id"
        class="step-item"
      >
        <span class="step-icon">{{ step.step }}</span>
        <span class="step-title">{{ step.title }}</span>
        <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
      </div>
    </div>
  </div>
</div>
```

**改动点 3**：添加样式

```css
/* 在 <style> 中添加 */
.thinking-panel {
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(100, 116, 139, 0.1);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  user-select: none;
}

.thinking-header:hover {
  color: #94a3b8;
}

.step-count {
  opacity: 0.7;
}

.thinking-steps {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  border-left: 2px solid #e2e8f0;
  margin-left: 4px;
  padding-left: 12px;
}

.step-item:first-child {
  margin-top: 4px;
}

.step-icon {
  font-size: 14px;
}

.step-title {
  color: #475569;
}

.step-detail {
  color: #94a3b8;
  font-size: 12px;
  margin-left: auto;
}
```

---

## 六、测试验证

### 6.1 后端测试

```bash
# 1. 启动后端服务
cd backend && source venv/bin/activate && python -m tars.main

# 2. 使用 test_ws.html 测试 WebSocket 事件
# 观察控制台是否输出 thinking_start, thinking_step, thinking_complete
```

### 6.2 前端测试

```bash
# 1. 启动前端服务
cd frontend && npm run dev

# 2. 打开 http://localhost:5173

# 3. 发送任意消息，观察：
#    - 消息气泡内是否显示"处理步骤"折叠区
#    - 点击是否可展开/收起
#    - 步骤列表是否正确显示图标和标题
```

### 6.3 验收检查清单

- [ ] 后端日志显示 thinking_* 事件发送
- [ ] 前端 WebSocket 控制台显示 thinking_* 事件接收
- [ ] 消息气泡显示折叠的处理步骤区域
- [ ] 点击可展开/收起
- [ ] 步骤列表显示正确的图标和标题
- [ ] 工具调用、记忆检索等步骤正确显示

---

## 七、风险与注意事项

### 7.1 风险

| 风险 | 缓解措施 |
|------|---------|
| WebSocket 事件过多导致性能问题 | 控制事件频率，避免每个小步骤都发送 |
| 前端状态管理复杂度增加 | 使用独立的 thinkingStates 对象隔离管理 |

### 7.2 注意事项

1. **事件顺序**：确保 `thinking_start` 在所有 `thinking_step` 之前，`thinking_complete` 在最后
2. **session 隔离**：不同 session 的 thinking 状态需要隔离管理
3. **清理机制**：对话结束后清理对应的 thinking 状态

---

*计划版本: v1.0*
*创建日期: 2026-05-10*
