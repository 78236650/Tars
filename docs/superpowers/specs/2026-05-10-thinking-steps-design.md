# 系统处理步骤显示设计（v2.6）

- **日期**：2026-05-10
- **版本**：v1.0（首发）
- **状态**：规划中
- **上游**：无

## 一、背景与目标

### 1.1 问题现状

用户在使用 TARS 聊天时，只能看到一个加载动画（旋转/脉冲），无法感知 Agent 内部的处理过程。这会导致：

- 用户不确定系统是否在正常工作
- 长等待时间让用户焦虑
- 无法了解 Agent 的决策过程

### 1.2 目标

在聊天界面中显示 Agent 的处理步骤，提供透明度，让用户了解：
- 当前正在检索记忆
- 正在调用哪些工具
- 正在激活哪些技能
- 正在调用 LLM 生成回答

### 1.3 非目标

- 不实现 LLM 思考链（如 Claude 的 extended thinking）
- 不修改 LLM 输出格式
- 不增加额外的网络开销

---

## 二、设计方案

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                         用户聊天界面                           │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ [TARS 消息内容...]                                      │   │
│  │                                                      │   │
│  │ ┌─ 🔄 处理步骤 ▼ ──────────────────────────────────┐ │   │
│  │ │  🔧 调用 web_search                              │ │   │
│  │ │  🧠 检索相关记忆                                  │ │   │
│  │ │  ⚡ 激活 code_assistant 技能                     │ │   │
│  │ └───────────────────────────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    WebSocket 事件流                           │
│  thinking_start → thinking_step → ... → thinking_complete     │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                      Agent 处理流程                           │
│  记忆检索 → 技能路由 → 工具调用 → LLM 生成                    │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 WebSocket 事件定义

#### 2.2.1 thinking_start

**触发时机**：Agent 开始处理用户消息

```json
{
  "type": "thinking_start",
  "session_id": "xxx",
  "timestamp": "2026-05-10T12:00:00.000+08:00"
}
```

#### 2.2.2 thinking_step

**触发时机**：每个处理步骤完成时

```json
{
  "type": "thinking_step",
  "session_id": "xxx",
  "step": "🔧",
  "title": "调用 web_search",
  "detail": "关键词: AI框架",
  "timestamp": "2026-05-10T12:00:00.123+08:00"
}
```

**step 图标规范**：

| 图标 | 含义 | 触发场景 |
|------|------|---------|
| 🔧 | 工具调用 | tool_calling 事件 |
| 🧠 | 记忆检索 | memory_router.retrieve() |
| 📝 | 记忆写入 | reflector.reflect() |
| ⚡ | 技能激活 | skill_router.route() |
| 💭 | 模型调用 | LLM 开始生成回答 |
| 📦 | 文件处理 | 文件上传/解析 |
| ⏳ | 等待中 | 长时间操作前的状态 |

#### 2.2.3 thinking_complete

**触发时机**：所有处理步骤完成，开始流式输出

```json
{
  "type": "thinking_complete",
  "session_id": "xxx",
  "timestamp": "2026-05-10T12:00:00.456+08:00"
}
```

---

## 三、后端实现

### 3.1 改动文件

| 文件 | 改动内容 |
|------|---------|
| `backend/tars/agent/agent.py` | 在关键节点发送 `thinking_*` 事件 |
| `backend/tars/tools/dispatcher.py` | 工具调用前后发送事件 |

### 3.2 agent.py 事件注入点

```python
# 1. handle_message 入口
await channel.send(session_id, {
    "type": "thinking_start",
    "session_id": session_id,
    "timestamp": now_iso(),
})

# 2. 记忆检索前
if self.memory_router:
    await channel.send(session_id, {
        "type": "thinking_step",
        "step": "🧠",
        "title": "检索相关记忆",
        "detail": f"查询: {query[:20]}...",
        ...
    })
    memories = self.memory_router.retrieve(query)

# 3. 技能路由前
if self.skill_router:
    await channel.send(session_id, {
        "type": "thinking_step",
        "step": "⚡",
        "title": "激活相关技能",
        ...
    })

# 4. chat_with_tools 调用前
await channel.send(session_id, {
    "type": "thinking_step",
    "step": "💭",
    "title": "生成回答",
    ...
})

# 5. 处理完成
await channel.send(session_id, {
    "type": "thinking_complete",
    ...
})
```

### 3.3 dispatcher.py 事件注入

在 `_call_with_native_tools` 和 `_call_with_prompt_fallback` 中：
- 工具调用前发送 `thinking_step`（从 on_tool_call 回调触发）
- 工具结果返回时发送 `thinking_step`（从 on_tool_result 回调触发）

---

## 四、前端实现

### 4.1 改动文件

| 文件 | 改动内容 |
|------|---------|
| `frontend/src/hooks/useWebSocket.ts` | 解析 `thinking_*` 事件 |
| `frontend/src/stores/wsStore.ts` | 存储 thinking 状态 |
| `frontend/src/components/chat/ChatPanel.vue` | 渲染折叠步骤组件 |

### 4.2 数据结构

```typescript
// wsStore.ts
interface ThinkingStep {
  id: string
  step: string      // 图标
  title: string     // 标题
  detail?: string   // 详细信息
  timestamp: string
}

interface ThinkingState {
  isActive: boolean
  steps: ThinkingStep[]
}

// message 类型扩展
interface Message {
  // ... 现有字段
  thinking?: ThinkingState
}
```

### 4.3 UI 组件结构

```
<assistant-message>
  <message-content>...</message-content>

  <!-- 新增：处理步骤折叠区 -->
  <div v-if="message.thinking" class="thinking-panel">
    <div class="thinking-header" @click="toggleThinking">
      <span>{{ isExpanded ? '▼' : '▶' }}</span>
      <span>🔄 处理步骤</span>
      <span class="step-count">({{ message.thinking.steps.length }})</span>
    </div>

    <div v-if="isExpanded" class="thinking-steps">
      <div v-for="step in message.thinking.steps" :key="step.id" class="step-item">
        <span class="step-icon">{{ step.step }}</span>
        <span class="step-title">{{ step.title }}</span>
        <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
      </div>
    </div>
  </div>
</assistant-message>
```

### 4.4 样式规范

```css
.thinking-panel {
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(100, 116, 139, 0.1);
  border-radius: 8px;
  font-size: 13px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #64748b;
  user-select: none;
}

.thinking-header:hover {
  color: #94a3b8;
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

.step-icon {
  font-size: 14px;
}

.step-title {
  color: #475569;
}

.step-detail {
  color: #94a3b8;
  font-size: 12px;
}
```

---

## 五、交互流程

### 5.1 时序图

```
用户: 发送消息
  │
  ▼
前端: 发送 WebSocket 消息
  │
  ▼
后端: 接收消息，发送 thinking_start
  │
  ├─► 记忆检索 → thinking_step(🧠)
  │
  ├─► 技能路由 → thinking_step(⚡)
  │
  ├─► 工具调用 → thinking_step(🔧) → tool_result → thinking_step(🔧)
  │
  ├─► LLM 生成 → thinking_step(💭)
  │
  ▼
后端: 发送 thinking_complete
  │
  ▼
后端: 开始流式输出 text_chunk
  │
  ▼
前端: 渲染消息内容 + 处理步骤（折叠）
```

### 5.2 默认状态

- **折叠**：用户需要点击展开查看步骤
- **历史消息**：已完成的消息保持展开状态（方便回顾）

---

## 六、兼容性

### 6.1 向后兼容

- 前端未处理 `thinking_*` 事件时：静默忽略，不影响现有功能
- 后端未发送 `thinking_*` 事件时：前端不显示步骤区域，保持原有行为

### 6.2 性能考虑

- `thinking_step` 事件批量发送，避免频繁 WebSocket 写入
- 前端使用虚拟列表处理大量步骤（理论上不会超过 20 个）

---

## 七、验收标准

### 7.1 功能验收

- [ ] 用户发送消息后，消息气泡内显示"处理步骤"折叠区
- [ ] 点击折叠区可展开/收起步骤列表
- [ ] 步骤列表显示图标、标题、详情
- [ ] 工具调用、记忆检索、技能激活等步骤正确显示
- [ ] 处理完成后，折叠区保持可见（可回顾）

### 7.2 兼容性验收

- [ ] 前端不处理 thinking 事件时不影响现有功能
- [ ] 移动端折叠区样式正常

### 7.3 性能验收

- [ ] WebSocket 事件不阻塞主响应
- [ ] 前端渲染无明显卡顿

---

*文档版本: v1.0*
*创建日期: 2026-05-10*
