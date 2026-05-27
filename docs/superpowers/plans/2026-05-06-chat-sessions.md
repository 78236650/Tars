---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Chat 多会话 + 历史记录 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Sidebar 中添加会话列表，支持新建/切换/删除多个独立对话，刷新后保留历史。

**Architecture:** 后端用现有 `sessions` + `messages` 表，加 list/delete/update_title 方法 + REST API。前端用 Pinia store 共享会话状态，Sidebar 渲染列表，ChatView 用 currentSessionId 关联 WebSocket 消息。

**Tech Stack:** FastAPI / SQLite / Pinia / Vue 3 / WebSocket

**Reference Spec:** [docs/superpowers/specs/2026-05-06-chat-sessions-design.md](../specs/2026-05-06-chat-sessions-design.md)

---

## 文件结构

```
新增：
  backend/tars/api/sessions.py                       (~80 行)
  backend/tests/test_sessions_api.py                 (~120 行)
  frontend/src/stores/chat.ts                        (~80 行)

修改：
  backend/tars/database/base.py                      (+30 行：3 个新方法)
  backend/tars/main.py                               (+2 行：注册 router)
  frontend/src/views/ChatView.vue                    (改造 sendMessage + 加载流程)
  frontend/src/components/layout/Sidebar.vue         (新增会话列表区块)
  frontend/src/api/index.ts                          (+30 行：sessionsApi)
  frontend/src/i18n/index.ts                         (+8 个 i18n keys)
```

---

## Task 1: Database — list/delete/update_title 方法

**Files:**
- Modify: `backend/tars/database/base.py`
- Test: `backend/tests/test_sessions_api.py`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_sessions_api.py`:
```python
"""Sessions API + Database 方法测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestDatabaseSessions:
    def test_list_sessions_returns_recent_first(self, tmp_path):
        from tars.database import Database
        import time
        db = Database(db_path=str(tmp_path / "t.db"))
        s1 = db.create_session(title="First")
        time.sleep(0.01)
        s2 = db.create_session(title="Second")
        time.sleep(0.01)
        s3 = db.create_session(title="Third")
        sessions = db.list_sessions()
        assert len(sessions) == 3
        assert sessions[0].id == s3.id
        assert sessions[2].id == s1.id

    def test_list_sessions_respects_limit(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        for i in range(5):
            db.create_session(title=f"Session {i}")
        sessions = db.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_delete_session_removes_messages(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        s = db.create_session(title="To delete")
        db.add_message(s.id, "user", "hello")
        db.add_message(s.id, "assistant", "hi")
        assert len(db.get_messages(s.id)) == 2
        ok = db.delete_session(s.id)
        assert ok is True
        assert db.get_session(s.id) is None
        assert len(db.get_messages(s.id)) == 0

    def test_delete_nonexistent_session(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        ok = db.delete_session("nonexistent-id")
        assert ok is False

    def test_update_session_title(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))
        s = db.create_session(title="Old Title")
        ok = db.update_session_title(s.id, "New Title")
        assert ok is True
        updated = db.get_session(s.id)
        assert updated.title == "New Title"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_sessions_api.py::TestDatabaseSessions -v
```
预期：FAIL（方法不存在）

- [ ] **Step 3: 在 Database 类中添加 3 个方法**

在 `backend/tars/database/base.py` 的 `get_messages` 方法之后（约 280 行附近），添加：

```python
    def list_sessions(self, user_id: str = "default", limit: int = 50) -> List[Session]:
        """按 updated_at 倒序返回会话列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        )
        sessions = []
        for row in cursor.fetchall():
            sessions.append(Session(
                id=row[0],
                agent_id=row[1],
                user_id=row[2],
                title=row[3],
                created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
                summary=row[6],
            ))
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话及关联消息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            return False
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return True

    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            return False
        now = get_local_now()
        cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )
        conn.commit()
        return True
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_sessions_api.py::TestDatabaseSessions -v
```
预期：5/5 PASS

- [ ] **Step 5: 跑现有测试无回归**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_memory_v2.py tests/test_memory_v3.py -v 2>&1 | tail -10
```
预期：现有测试仍通过

---

## Task 2: REST API — sessions router

**Files:**
- Create: `backend/tars/api/sessions.py`
- Modify: `backend/tars/main.py`
- Test: `backend/tests/test_sessions_api.py`

- [ ] **Step 1: 写测试**

追加到 `tests/test_sessions_api.py`:
```python
class TestSessionsAPI:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """创建带独立 DB 的测试 client"""
        from fastapi.testclient import TestClient
        # 用 monkeypatch 切到临时 DB
        monkeypatch.setenv("TARS_DB_PATH", str(tmp_path / "t.db"))
        # 重置全局 db 实例
        import importlib
        from tars import database
        importlib.reload(database)
        from tars.main import app
        return TestClient(app)

    def test_create_session(self, client):
        resp = client.post("/api/sessions/")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "New Chat"

    def test_list_sessions(self, client):
        client.post("/api/sessions/")
        client.post("/api/sessions/")
        resp = client.get("/api/sessions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_messages_empty(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.get(f"/api/sessions/{s['id']}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_messages_nonexistent(self, client):
        resp = client.get("/api/sessions/nonexistent/messages")
        assert resp.status_code == 404

    def test_delete_session(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.delete(f"/api/sessions/{s['id']}")
        assert resp.status_code == 200
        # 再列出应空
        listing = client.get("/api/sessions/").json()
        assert all(item["id"] != s["id"] for item in listing)

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404

    def test_update_title(self, client):
        s = client.post("/api/sessions/").json()
        resp = client.patch(f"/api/sessions/{s['id']}", json={"title": "FastAPI 项目"})
        assert resp.status_code == 200
        # 再 list 应显示新标题
        listing = client.get("/api/sessions/").json()
        target = next(x for x in listing if x["id"] == s["id"])
        assert target["title"] == "FastAPI 项目"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_sessions_api.py::TestSessionsAPI -v
```
预期：FAIL（router 不存在 → 404 / import 失败）

- [ ] **Step 3: 创建 sessions API**

创建 `backend/tars/api/sessions.py`:
```python
"""Sessions REST API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..database import Database

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_db: Optional[Database] = None


def init_sessions_api(db: Database):
    global _db
    _db = db


class TitleUpdateRequest(BaseModel):
    title: str


def _session_to_dict(s):
    return {
        "id": s.id,
        "title": s.title,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m):
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
    }


@router.get("/")
def list_sessions():
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return [_session_to_dict(s) for s in _db.list_sessions()]


@router.post("/")
def create_session():
    if not _db:
        raise HTTPException(500, "DB not initialized")
    s = _db.create_session(title="New Chat")
    return _session_to_dict(s)


@router.get("/{session_id}/messages")
def get_session_messages(session_id: str):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    if not _db.get_session(session_id):
        raise HTTPException(404, "Session not found")
    return [_message_to_dict(m) for m in _db.get_messages(session_id)]


@router.delete("/{session_id}")
def delete_session(session_id: str):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}


@router.patch("/{session_id}")
def update_session_title(session_id: str, payload: TitleUpdateRequest):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    ok = _db.update_session_title(session_id, payload.title)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"success": True}
```

- [ ] **Step 4: 在 main.py 注册 router**

修改 `backend/tars/main.py`：

在 import 块（约 35 行附近）添加：
```python
from tars.api.sessions import router as sessions_router, init_sessions_api
```

在 `app.include_router(...)` 块的最后（约 140 行附近）添加：
```python
app.include_router(sessions_router)
init_sessions_api(db)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_sessions_api.py::TestSessionsAPI -v
```
预期：7/7 PASS

如果测试因为全局 DB 单例导致的隔离问题失败，简化测试：直接调用 `_db = Database(...)` + `init_sessions_api(_db)` 而不是 reload。把 fixture 改为：
```python
@pytest.fixture
def client(self, tmp_path):
    from fastapi.testclient import TestClient
    from tars.database import Database
    from tars.api.sessions import init_sessions_api, router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    db = Database(db_path=str(tmp_path / "t.db"))
    init_sessions_api(db)
    return TestClient(app)
```

- [ ] **Step 6: 手动验证 API 可用**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -c "
from tars.main import app
print('Routes:')
for route in app.routes:
    if hasattr(route, 'path') and 'session' in route.path:
        print(f'  {route.methods} {route.path}')
"
```
预期：列出 5 条 session 相关路由

---

## Task 3: 前端 API 层 — sessionsApi

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 在 types/index.ts 加类型**

在 `frontend/src/types/index.ts` 末尾追加：
```typescript
export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatHistoryMessage {
  id: string
  role: string
  content: string
  timestamp: string
}
```

- [ ] **Step 2: 在 api/index.ts 加 sessionsApi**

在 `frontend/src/api/index.ts` 文件末尾（在 `export default api` 之前）追加：
```typescript
export const sessionsApi = {
  list: async (): Promise<ChatSession[]> => {
    const response = await api.get<ChatSession[]>('/sessions/')
    return response.data
  },

  create: async (): Promise<ChatSession> => {
    const response = await api.post<ChatSession>('/sessions/')
    return response.data
  },

  getMessages: async (id: string): Promise<ChatHistoryMessage[]> => {
    const response = await api.get<ChatHistoryMessage[]>(`/sessions/${id}/messages`)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/sessions/${id}`)
  },

  updateTitle: async (id: string, title: string): Promise<void> => {
    await api.patch(`/sessions/${id}`, { title })
  },
}
```

需要在 import 顶部加上类型：
```typescript
import type {
  User,
  // ... 现有的
  ChatSession,
  ChatHistoryMessage,
} from '@/types'
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```
预期：无错误

---

## Task 4: 前端 Pinia store — chat

**Files:**
- Create: `frontend/src/stores/chat.ts`

- [ ] **Step 1: 创建 store**

创建 `frontend/src/stores/chat.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi } from '@/api'
import type { ChatSession } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)

  const loadSessions = async () => {
    sessions.value = await sessionsApi.list()
  }

  const createSession = async (): Promise<ChatSession> => {
    const s = await sessionsApi.create()
    sessions.value.unshift(s)
    currentSessionId.value = s.id
    return s
  }

  const switchSession = (id: string) => {
    currentSessionId.value = id
  }

  const deleteSession = async (id: string) => {
    await sessionsApi.delete(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value[0]?.id ?? null
    }
  }

  const updateTitle = async (id: string, title: string) => {
    await sessionsApi.updateTitle(id, title)
    const target = sessions.value.find(s => s.id === id)
    if (target) target.title = title
  }

  const initIfEmpty = async () => {
    await loadSessions()
    if (sessions.value.length === 0) {
      await createSession()
    } else if (!currentSessionId.value) {
      currentSessionId.value = sessions.value[0].id
    }
  }

  return {
    sessions,
    currentSessionId,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
    updateTitle,
    initIfEmpty,
  }
})
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```
预期：无错误

---

## Task 5: i18n 增加 session 相关 keys

**Files:**
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: 加 keys**

定位 `frontend/src/i18n/index.ts` 中的中文 messages 对象（搜索 `zh:`），在合适位置（chat 段落或新建 sidebar 段落）加：
```typescript
chat: {
  // ... 现有 keys
  newChat: '新对话',
  noSessions: '暂无会话',
  deleteConfirm: '确定删除该会话？',
  sessionDeleted: '会话已删除',
}
```

英文 messages 对象（`en:`）对应：
```typescript
chat: {
  // ... existing
  newChat: 'New Chat',
  noSessions: 'No sessions yet',
  deleteConfirm: 'Delete this session?',
  sessionDeleted: 'Session deleted',
}
```

注意：如果 `chat` 子对象已存在，把 4 个新 key 合并进去；不存在则新建。

- [ ] **Step 2: 验证编译**

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```
预期：无错误

---

## Task 6: Sidebar 加会话列表 UI

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.vue`

- [ ] **Step 1: 在 script setup 顶部引入 store**

在 `frontend/src/components/layout/Sidebar.vue` 的 script setup 块中（现有 import 之后），添加：
```typescript
import { useChatStore } from '@/stores/chat'
import { onMounted } from 'vue'

const chatStore = useChatStore()

onMounted(async () => {
  // 现有逻辑保留
  await chatStore.loadSessions()
})

const newChat = async () => {
  await chatStore.createSession()
}

const switchSession = (id: string) => {
  chatStore.switchSession(id)
}

const deleteSession = async (id: string, e: Event) => {
  e.stopPropagation()
  if (!confirm(t('chat.deleteConfirm'))) return
  try {
    await chatStore.deleteSession(id)
    toast.success(t('chat.sessionDeleted'))
  } catch (err) {
    toast.error(t('common.failed') || 'Failed')
  }
}

const truncate = (s: string, n = 22) => s.length > n ? s.slice(0, n) + '...' : s
```

注意：`onMounted` 已被 settingsStore 使用，把 `chatStore.loadSessions()` 加到现有 `onMounted` 内部即可，不要重复调用 `onMounted`。

修改现有 onMounted（如果存在）为：
```typescript
onMounted(async () => {
  const saved = localStorage.getItem('sidebar_collapsed')
  if (saved === 'true') collapsed.value = true
  settingsStore.loadModels()
  await chatStore.loadSessions()
})
```

- [ ] **Step 2: 在 template 的 nav 之后插入会话列表区块**

在 `<nav class="flex-1 p-2">` 关闭标签之后、模型切换 div 之前插入：

```vue
<!-- 会话列表（仅展开模式 + 仅 Chat 路由时显示完整） -->
<div v-if="!collapsed" class="border-t border-slate-700 flex flex-col" style="max-height: 40%;">
  <div class="p-2">
    <button
      @click="newChat"
      class="w-full px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm flex items-center justify-center gap-2 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
      </svg>
      {{ t('chat.newChat') }}
    </button>
  </div>

  <div class="overflow-y-auto px-2 pb-2 flex-1">
    <p v-if="chatStore.sessions.length === 0" class="text-xs text-slate-500 text-center py-4">
      {{ t('chat.noSessions') }}
    </p>
    <button
      v-for="session in chatStore.sessions"
      :key="session.id"
      @click="switchSession(session.id)"
      class="group w-full px-3 py-2 mb-1 rounded-lg text-left text-sm flex items-center justify-between transition-colors"
      :class="chatStore.currentSessionId === session.id
        ? 'bg-blue-600 text-white'
        : 'text-slate-300 hover:bg-slate-700'"
    >
      <span class="truncate flex-1">{{ truncate(session.title) }}</span>
      <span
        @click="deleteSession(session.id, $event)"
        class="opacity-0 group-hover:opacity-100 ml-2 text-slate-400 hover:text-red-400 transition-opacity"
        :title="t('chat.deleteConfirm')"
      >
        ×
      </span>
    </button>
  </div>
</div>

<!-- 折叠模式下只显示新建按钮 -->
<div v-else class="border-t border-slate-700 p-2">
  <button
    @click="newChat"
    class="w-full p-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center"
    :title="t('chat.newChat')"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
    </svg>
  </button>
</div>
```

- [ ] **Step 3: 启动前端 dev server 视觉验证**

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run dev > /tmp/vite.log 2>&1 &
sleep 3
echo "Dev server should be running. Check http://localhost:5173"
```

验证项：
- Sidebar 出现"+ 新对话"按钮
- 点击创建后会话出现在列表中
- 折叠模式下只显示 + 图标按钮

---

## Task 7: ChatView 用 store + 加载历史

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: 在 script setup 顶部引入 store + watch**

`frontend/src/views/ChatView.vue` 的 script setup 中，加 import：
```typescript
import { useChatStore } from '@/stores/chat'
import { watch, ref, onMounted, onUnmounted } from 'vue'
import { sessionsApi } from '@/api'
```

并新增：
```typescript
const chatStore = useChatStore()
```

- [ ] **Step 2: 修改 onMounted 初始化会话**

替换现有 `onMounted`：
```typescript
onMounted(async () => {
  settingsStore.loadModels()
  await chatStore.initIfEmpty()
  if (chatStore.currentSessionId) {
    await loadSessionMessages(chatStore.currentSessionId)
  }
  connectWebSocket()
})

const loadSessionMessages = async (sessionId: string) => {
  try {
    const history = await sessionsApi.getMessages(sessionId)
    messages.value = history.map(m => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
    }))
  } catch (e) {
    console.error('加载会话历史失败', e)
    messages.value = []
  }
}
```

- [ ] **Step 3: 监听会话切换**

在 onMounted 之后添加：
```typescript
watch(() => chatStore.currentSessionId, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await loadSessionMessages(newId)
  } else if (!newId) {
    messages.value = []
  }
})
```

- [ ] **Step 4: 修改 sendMessage 用 currentSessionId**

替换原 `sendMessage`：
```typescript
const sendMessage = async () => {
  if ((!inputMessage.value.trim() && attachments.value.length === 0) || !ws) return
  if (!chatStore.currentSessionId) {
    console.warn('No active session')
    return
  }

  const sessionId = chatStore.currentSessionId
  const messageId = Date.now().toString()
  const messageContent = inputMessage.value
  const isFirstMessage = messages.value.length === 0

  messages.value.push({
    id: messageId,
    role: 'user',
    content: messageContent,
    timestamp: new Date().toISOString(),
    attachments: attachments.value.length > 0 ? [...attachments.value] : undefined,
  })

  isGenerating.value = true

  const payload: any = {
    session_id: sessionId,
    content: messageContent,
  }
  if (attachments.value.length > 0) {
    payload.file_ids = attachments.value.map(a => a.file_id)
  }

  ws.send(JSON.stringify(payload))

  inputMessage.value = ''
  attachments.value = []

  // 第一条消息后用前 30 字作标题
  if (isFirstMessage && messageContent.trim()) {
    const newTitle = messageContent.trim().slice(0, 30)
    try {
      await chatStore.updateTitle(sessionId, newTitle)
    } catch (e) {
      console.error('更新标题失败', e)
    }
  }
}
```

- [ ] **Step 5: WebSocket 接收逻辑用 sessionId 关联消息**

定位 `ws.onmessage` 中 `text_chunk` 处理（约 39-51 行），把 `data.session_id` 用法保持，但要确保它和 `chatStore.currentSessionId` 一致才合并。改为：
```typescript
if (data.type === 'text_chunk') {
  isGenerating.value = true
  if (data.session_id !== chatStore.currentSessionId) {
    return  // 旧会话的残留事件，忽略
  }
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === `streaming-${data.session_id}`) {
    lastMsg.content += data.content
  } else {
    messages.value.push({
      id: `streaming-${data.session_id}`,
      role: 'assistant',
      content: data.content,
      timestamp: data.timestamp,
    })
  }
}
```

注：原代码用 `data.session_id` 作为消息 id 容易和真实历史 id 冲突，这里改用 `streaming-${session_id}` 前缀避免冲突。

定位 `done` 事件处理（搜索 `'done'`）：处理完后，给最后一条 assistant 消息分配真实 id（用 timestamp）：
```typescript
} else if (data.type === 'done') {
  isGenerating.value = false
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.id?.startsWith('streaming-')) {
    lastMsg.id = `msg-${Date.now()}`
  }
}
```

- [ ] **Step 6: 编译并视觉验证**

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npx vue-tsc --noEmit 2>&1 | tail -10
```
预期：无错误

启动 dev server 验证：
- 加载页面后自动有当前会话
- 发消息后第一条用户消息前 30 字成为会话标题
- 点击其他会话切换时，消息列表替换为该会话历史
- 点"新对话"创建新会话，消息清空
- 删除当前会话后切换到下一个或新建

---

## Task 8: 后端冒烟集成测试

**Files:**
- Test: `backend/tests/test_sessions_api.py`

- [ ] **Step 1: 加端到端 WebSocket 测试**

追加到 `tests/test_sessions_api.py`:
```python
class TestEndToEnd:
    def test_full_lifecycle(self, tmp_path):
        """创建会话 → 通过 add_message 模拟 → 列出 → 删除"""
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "t.db"))

        # 创建
        s = db.create_session(title="Test")
        assert s.id

        # 加消息
        db.add_message(s.id, "user", "Hello")
        db.add_message(s.id, "assistant", "Hi!")
        msgs = db.get_messages(s.id)
        assert len(msgs) == 2

        # 更新标题
        db.update_session_title(s.id, "Hello topic")
        assert db.get_session(s.id).title == "Hello topic"

        # 列表
        sessions = db.list_sessions()
        assert any(x.id == s.id for x in sessions)

        # 删除
        db.delete_session(s.id)
        assert db.get_session(s.id) is None
        assert len(db.get_messages(s.id)) == 0
```

- [ ] **Step 2: 跑全部测试**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/test_sessions_api.py -v
```
预期：全部 PASS（5 + 7 + 1 = 13 个）

- [ ] **Step 3: 跑现有测试无回归**

```bash
cd /Users/daobanxiang/myproject/TARS/backend && ./venv/bin/python -m pytest tests/ -v 2>&1 | tail -20
```
预期：除了已知预先存在的失败外，全部 PASS

---

## Task 9: 文档更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README**

在 `/Users/daobanxiang/myproject/TARS/README.md` 中找到 "## API 文档" 章节，在工具/技能 API 表格之前或之后新增：

```markdown
### 会话管理 `/api/sessions/`

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/sessions/` | 列出会话（按 updated_at 倒序） |
| POST | `/api/sessions/` | 创建新会话 |
| GET | `/api/sessions/{id}/messages` | 获取会话历史消息 |
| DELETE | `/api/sessions/{id}` | 删除会话 + 关联消息 |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |
```

并在"前端升级"段落中添加一行：
```markdown
- 会话列表（Sidebar 内）支持多会话独立历史 + 新建/切换/删除
```

---

## 自检 Checklist

完成后逐条验证（Spec 对应关系）：

- ✅ Task 1 → Spec §3.1（Database 方法）
- ✅ Task 2 → Spec §3.2（REST API）
- ✅ Task 3 → Spec §3.6（前端 API 层）
- ✅ Task 4 → Spec §3.6（Pinia store）
- ✅ Task 5 → Spec §3.4（i18n 文案）
- ✅ Task 6 → Spec §3.4（Sidebar UI）
- ✅ Task 7 → Spec §3.5 + §3.7（ChatView 改造 + 标题生成）
- ✅ Task 8 → 集成测试
- ✅ Task 9 → 文档同步

成功标准（手动验证）：
1. 新建对话 → 出现在 Sidebar 列表，shown as "New Chat"
2. 发送消息 → 标题变为消息前 30 字
3. 切换到另一个会话 → 消息列表替换
4. 刷新页面 → 当前会话历史保留
5. 删除会话 → 列表移除；若是当前会话则切换/新建
