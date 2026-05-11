# 处理流程流式显示 + 任务内嵌设计（v2.6.1）

- **日期**：2026-05-11
- **版本**：v1.0
- **状态**：实施中
- **上游**：`2026-05-10-thinking-steps-design.md`（v2.6）

## 一、背景

v2.6 实现了处理步骤显示，但采用缓冲模式——`thinking_step` 事件到达后暂存在 `pendingThinking`，等首个 `text_chunk` 到达才附加到 assistant 消息。用户等待期间看不到任何进度，体验不佳。

同时，v2.4 的 TaskPanel 右侧抽屉组件触发频率极低（需 `/plan` 或特定关键词），与聊天流脱节，后端多个任务事件（`step_verified`、`step_retrying`）在前端未被消费。

## 二、目标

1. **流式处理步骤**：`thinking_start` 立即在聊天流中显示步骤面板，随 `thinking_step` 事件逐条追加，`thinking_complete` 时标记完成
2. **内嵌任务进度**：去掉 TaskPanel 抽屉，任务创建时在聊天流中插入任务卡片，随后端事件实时更新步骤状态
3. **精简 UI**：移除 TaskPanel.vue 组件及相关集成代码

## 三、流式处理步骤

### 3.1 交互流程

```
thinking_start 到达
  → 在 messages 数组末尾插入一条 assistant 占位消息（content 为空，thinking 已初始化）
  → 消息气泡内显示 "🔄 处理中..." + 脉冲动画

thinking_step 到达
  → 追加步骤到该消息的 thinking.steps
  → 步骤列表实时展开（不折叠）

thinking_complete 到达
  → thinking.isActive = false
  → 折叠按钮出现

首个 text_chunk 到达
  → 开始填充消息 content
  → 继续流式追加文本
```

### 3.2 ChatView.vue 改动

```typescript
// 删除 pendingThinking 缓冲机制

// 新增：thinking_start 时创建占位消息
if (data.type === 'thinking_start') {
  const streamId = `streaming-${data.session_id}`
  messages.value.push({
    id: streamId,
    role: 'assistant',
    content: '',
    timestamp: data.timestamp,
    thinking: { isActive: true, steps: [] }
  })
}

// thinking_step：追加到最近一条 assistant 消息的 thinking.steps
if (data.type === 'thinking_step') {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.thinking) {
    last.thinking.steps.push({ ... })
  }
}

// text_chunk：追加到已有消息（已在 thinking_start 时创建）
```

### 3.3 ChatPanel.vue 改动

- 处理步骤面板默认展开（`isActive === true` 时），完成后再折叠
- 空白内容时显示脉冲动画

## 四、内嵌任务进度

### 4.1 事件流

```
task_created → 插入任务卡片消息
step_verified / step_retrying → 更新对应任务卡片的步骤状态
task_completed → 卡片标记完成，展示产出
task_aborted → 卡片标记中止
plan_step_failed → 卡片显示失败步骤
```

### 4.2 新增组件

`frontend/src/components/chat/TaskCard.vue` — 内嵌任务进度卡片：

- 标题 + 状态徽章
- 步骤列表（图标 + 描述 + 状态颜色）
- 进度条
- 完成后展示 artifacts + output_summary
- 操作按钮：暂停/恢复/取消/重试（仅 running/paused 状态）

### 4.3 数据结构

```typescript
interface TaskMessage {
  id: string
  role: 'task'
  task: {
    id: string
    title: string
    goal: string
    status: string
    current_step: number
    total_steps: number
    steps: TaskStep[]
    artifacts?: string[]
    output_summary?: string
  }
  timestamp: string
}
```

## 五、删除项

| 文件 | 操作 |
|------|------|
| `frontend/src/components/chat/TaskPanel.vue` | **删除** |
| `frontend/src/views/ChatView.vue` | 移除 TaskPanel 导入、tasks ref、task 操作函数、模板引用约 80 行 |

## 六、改动清单

| 文件 | 改动 |
|------|------|
| `ChatView.vue` | 流式 thinking + 内嵌任务卡片事件处理 + 删除 TaskPanel |
| `ChatPanel.vue` | 处理步骤默认展开 / 空内容脉冲动画 |
| `TaskCard.vue` | **新增** — 内嵌任务进度卡片 |
| `TaskPanel.vue` | **删除** |

## 七、验收

- [ ] 发送消息后，处理步骤面板立即出现并逐条追加
- [ ] LLM 开始输出后，步骤面板保持在消息上方
- [ ] 触发任务时，聊天流中出现任务进度卡片
- [ ] 任务步骤状态随执行实时更新
- [ ] 右侧抽屉不再出现
- [ ] 任务卡片完成后展示产出摘要

---

*文档版本: v1.0*
*创建日期: 2026-05-11*
