---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 流式处理 + 任务内嵌实施计划（v2.6.1）

- **日期**：2026-05-11
- **版本**：v1.0
- **上游设计**：`2026-05-11-streaming-processing-design.md`
- **状态**：实施中

## 一、实施概览

### 1.1 改动范围

| 层级 | 文件 | 改动类型 |
|------|------|---------|
| 前端 | `frontend/src/views/ChatView.vue` | 修改 |
| 前端 | `frontend/src/components/chat/ChatPanel.vue` | 修改 |
| 前端 | `frontend/src/components/chat/TaskCard.vue` | **新增** |
| 前端 | `frontend/src/components/chat/TaskPanel.vue` | **删除** |

### 1.2 实施顺序

1. **Phase 1**: ChatView.vue — 流式 thinking + 内嵌任务事件处理 + 删除 TaskPanel 代码
2. **Phase 2**: ChatPanel.vue — 处理步骤默认展开 + 空内容脉冲 + 任务卡片渲染
3. **Phase 3**: 新增 TaskCard.vue 内嵌任务进度卡片
4. **Phase 4**: 删除 TaskPanel.vue
5. **Phase 5**: 端到端验证

---

## 二、Phase 1: ChatView.vue 重构

### 2.1 流式 thinking 改动

**删除** `pendingThinking` ref 及相关缓冲逻辑。

**thinking_start 处理**：不再缓冲，直接创建占位 assistant 消息。

```typescript
} else if (data.type === 'thinking_start') {
  const streamId = `streaming-${data.session_id}`
  messages.value.push({
    id: streamId,
    role: 'assistant',
    content: '',
    timestamp: data.timestamp,
    thinking: { isActive: true, steps: [] }
  })
}
```

**thinking_step 处理**：追加到最后一条 assistant 消息的 thinking.steps。

```typescript
} else if (data.type === 'thinking_step') {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.thinking) {
    last.thinking.steps.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      step: data.step || '',
      title: data.title || '',
      detail: data.detail,
      timestamp: data.timestamp || ''
    })
  }
}
```

**thinking_complete 处理**：标记 isActive = false。

```typescript
} else if (data.type === 'thinking_complete') {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant' && messages.value[i].thinking) {
      messages.value[i].thinking.isActive = false
      break
    }
  }
}
```

**text_chunk 处理**：流式追加到已有占位消息。

```typescript
if (data.type === 'text_chunk') {
  const streamId = `streaming-${data.session_id}`
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === streamId) {
    lastMsg.content += data.content
  }
  // 不再 else 创建新消息（已在 thinking_start 时创建）
}
```

### 2.2 内嵌任务事件处理

新增 `task_created`/`task_updated` → 插入任务卡片消息，而非打开抽屉。

```typescript
} else if (data.type === 'task_created' || data.type === 'task_updated') {
  const t = data.payload?.task || data.task
  if (!t) return
  const existing = messages.value.find(m => m.task?.id === t.id)
  if (existing) {
    existing.task = t
  } else {
    messages.value.push({
      id: `task-${t.id}`,
      role: 'task',
      content: '',
      timestamp: data.timestamp,
      task: t
    })
  }
}
```

新增 `step_verified`/`step_retrying`/`plan_step_failed` → 更新任务卡片步骤状态。

```typescript
} else if (data.type === 'step_verified' || data.type === 'step_retrying' || data.type === 'plan_step_failed') {
  // 更新对应任务步骤状态（task_created 时已插入卡片）
}
```

### 2.3 删除 TaskPanel 相关代码

- 删除 `import TaskPanel`
- 删除 `tasks` ref、`showTaskPanel` ref
- 删除 `toggleTaskPanel`、`doPauseTask`、`doResumeTask`、`doCancelTask`、`doRetryTask`
- 删除模板中 `<TaskPanel>` 引用
- 删除 Header 中的任务按钮

---

## 三、Phase 2: ChatPanel.vue 改动

### 3.1 处理步骤默认展开

当 `thinking.isActive === true` 时，处理步骤面板始终展开（不依赖 `expandedThinking`）。

```vue
<div v-if="msg.thinking && msg.thinking.steps.length > 0" class="mt-3">
  <div class="thinking-panel" @click="msg.thinking.isActive ? null : toggleThinking(msg.id)">
    <div class="thinking-header">
      <span>{{ msg.thinking.isActive ? '▼' : isThinkingExpanded(msg.id) ? '▼' : '▶' }}</span>
      <span>🔄 {{ msg.thinking.isActive ? '处理中...' : '处理步骤' }}</span>
      <span class="step-count">({{ msg.thinking.steps.length }})</span>
    </div>
    <div v-if="msg.thinking.isActive || isThinkingExpanded(msg.id)" class="thinking-steps">
      ...
    </div>
  </div>
</div>
```

### 3.2 空内容脉冲动画

当 `msg.content === ''` 且 `msg.thinking?.isActive` 时，显示脉冲点。

```vue
<div v-if="!msg.content && msg.thinking?.isActive" class="flex gap-1 py-2">
  <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />
  <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.2s" />
  <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.4s" />
</div>
```

### 3.3 任务卡片渲染

任务消息（`msg.role === 'task'`）时渲染 TaskCard 组件。

```vue
<TaskCard v-if="msg.role === 'task'" :task="msg.task" />
```

---

## 四、Phase 3: TaskCard.vue（新增）

内嵌任务进度卡片组件，精简版 TaskPanel：

- Props: `task: Task`
- 状态徽章 + 标题
- 步骤列表（图标 + 描述 + 颜色）
- 进度条
- 完成后 artifacts / output_summary
- 操作按钮（running: 暂停+取消, paused: 恢复+取消）

---

## 五、Phase 4: 删除文件

```bash
rm frontend/src/components/chat/TaskPanel.vue
```

---

## 六、测试验证

### 6.1 流式步骤

```bash
cd backend && python3 -m tars.main &
cd frontend && npm run dev
```

1. 打开 http://localhost:5173
2. 发送消息
3. 验证：消息气泡立即出现，步骤逐条追加，LLM 文本到达后开始填充内容

### 6.2 任务卡片

1. 输入 `/plan 创建测试文件`
2. 验证：聊天流中出现任务卡片，步骤状态随执行更新

### 6.3 验收清单

- [ ] thinking_start 到达后聊天流立刻出现占位消息
- [ ] 步骤逐条追加，面板展开
- [ ] thinking_complete 后面板可折叠
- [ ] text_chunk 正确追加到占位消息
- [ ] 任务触发时聊天流出现任务卡片（无右侧抽屉）
- [ ] 任务步骤状态实时更新
- [ ] TaskPanel.vue 已删除，无残留引用
- [ ] Header 无任务按钮

---

*计划版本: v1.0*
*创建日期: 2026-05-11*
