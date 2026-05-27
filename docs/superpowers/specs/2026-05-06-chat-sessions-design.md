---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Chat 多会话 + 历史记录 设计文档

**日期：** 2026-05-06
**状态：** Approved

## 1. 目标

让用户可以创建多个独立对话，保留聊天历史，刷新页面后可恢复。在 Sidebar 中展示会话列表，支持新建、切换、删除。

## 2. 当前状态

- 后端已有 `sessions` 表（id, user_id, title, created_at, updated_at）和 `messages` 表（session_id 外键）
- 后端有 `create_session`、`get_session`、`get_messages`、`add_message` 方法
- 后端没有 `list_sessions`、`delete_session` 方法，没有 session REST API
- 前端 ChatView 用 `Date.now()` 当 session_id，刷新即丢失
- Sidebar 只有导航 + 模型切换，没有会话列表

## 3. 设计

### 3.1 后端 — Database 新增方法

在 `backend/tars/database/base.py` 的 Database 类中新增：

```python
def list_sessions(self, user_id: str = "default", limit: int = 50) -> List[Session]:
    """按 updated_at 倒序返回会话列表"""

def delete_session(self, session_id: str) -> bool:
    """删除会话及其所有关联消息，返回是否成功"""

def update_session_title(self, session_id: str, title: str) -> bool:
    """更新会话标题"""
```

### 3.2 后端 — REST API

新建 `backend/tars/api/sessions.py`，注册到 FastAPI app：

| 方法 | 路径 | 描述 | 返回 |
|------|------|------|------|
| GET | `/api/sessions/` | 列出会话（按 updated_at 倒序） | `[{id, title, created_at, updated_at}]` |
| POST | `/api/sessions/` | 创建新会话 | `{id, title, created_at}` |
| GET | `/api/sessions/{id}/messages` | 获取会话历史消息 | `[{id, role, content, timestamp}]` |
| DELETE | `/api/sessions/{id}` | 删除会话 + 关联消息 | `{success: true}` |
| PATCH | `/api/sessions/{id}` | 更新标题 | `{success: true}` |

### 3.3 后端 — WebSocket 改造

当前前端发送：
```json
{"session_id": "1717654321000", "content": "hello"}
```

改为前端发送真实 session_id（UUID）。后端 `handle_message` 已经用 `message.session_id` 存取消息，无需改后端逻辑，只需前端传正确的 ID。

### 3.4 前端 — Sidebar 会话列表

在 Sidebar 的导航列表（`<nav>`）下方、模型切换区域上方，插入会话列表区块：

```
┌─────────────────────┐
│ TARS Agent          │
├─────────────────────┤
│ 💬 Chat             │  ← 导航
│ 🔧 Tools            │
│ ⚙️ Settings         │
├─────────────────────┤
│ [+ 新对话]          │  ← 新增
│ ─────────────────── │
│ ● FastAPI 脚手架... │  ← 当前会话（高亮）
│   五子棋实现...     │
│   记忆系统讨论...   │
│   ...               │
├─────────────────────┤
│ 模型切换区域        │
└─────────────────────┘
```

- 每条会话：显示 title（最多 20 字截断 + `...`），hover 时右侧出现 `×` 删除按钮
- 当前会话蓝色背景高亮
- 列表区域可滚动（`max-h` + `overflow-y-auto`）
- collapsed 模式下：只显示 `+` 图标按钮

### 3.5 前端 — ChatView 改造

1. **状态管理：** 在 ChatView 中新增：
   - `currentSessionId: ref<string | null>(null)`
   - `sessions: ref<Session[]>([])`

2. **页面加载流程：**
   - `onMounted` → `GET /api/sessions/` 获取列表
   - 若列表非空 → 取第一条（最近的）作为 currentSessionId → 加载其消息
   - 若列表为空 → 自动创建新会话

3. **新建对话：**
   - `POST /api/sessions/` → 拿到新 session_id
   - 清空 messages
   - 设置 currentSessionId
   - 列表头部插入新会话

4. **切换会话：**
   - 设置 currentSessionId
   - `GET /api/sessions/{id}/messages` → 替换 messages

5. **发消息：**
   - WebSocket payload 使用 `currentSessionId`
   - 第一条消息发出后，若 title 仍为 "New Chat"，用 `content.slice(0, 30)` 调 `PATCH /api/sessions/{id}` 更新标题，同时更新本地列表

6. **删除会话：**
   - `confirm()` 确认
   - `DELETE /api/sessions/{id}`
   - 从列表移除
   - 若删的是当前会话 → 切换到列表第一条，若列表空则新建

### 3.6 状态共享

ChatView 和 Sidebar 需要共享 `sessions` 列表和 `currentSessionId`。方案：

使用 Pinia store `stores/chat.ts`：
- `sessions: Session[]`
- `currentSessionId: string | null`
- `loadSessions()`
- `createSession()`
- `switchSession(id)`
- `deleteSession(id)`
- `updateTitle(id, title)`

ChatView 和 Sidebar 都从这个 store 读取/操作。

### 3.7 会话标题生成

- 创建时 title = "New Chat"
- 第一条用户消息发出后，前端取 `content.slice(0, 30)` 作为标题
- 调 `PATCH /api/sessions/{id}` 更新后端
- 更新本地 store 中对应 session 的 title

## 4. 文件结构

```
新增：
  backend/tars/api/sessions.py          — Session REST API
  frontend/src/stores/chat.ts           — Chat Pinia store

修改：
  backend/tars/database/base.py         — 新增 list/delete/update_title 方法
  backend/tars/main.py                  — 注册 sessions router
  frontend/src/views/ChatView.vue       — 使用 store + currentSessionId
  frontend/src/components/layout/Sidebar.vue — 会话列表 UI
  frontend/src/i18n/index.ts            — 新增 i18n keys
  frontend/src/api/index.ts             — 新增 sessionsApi（如果有的话）
```

## 5. 测试

- `test_sessions_api.py`：
  - 创建会话 → 返回 id + title
  - 列出会话 → 按 updated_at 倒序
  - 获取消息 → 返回正确的历史
  - 删除会话 → 消息也被删除
  - 更新标题 → 生效

## 6. 范围之外

- ❌ 会话搜索
- ❌ 会话置顶/收藏
- ❌ 会话导出
- ❌ 会话重命名（手动编辑标题）— 只有自动标题
- ❌ 多用户隔离（当前仍假设单用户 "default"）
