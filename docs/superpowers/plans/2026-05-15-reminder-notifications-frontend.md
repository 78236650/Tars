---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Reminder Notifications Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在聊天页补齐 reminder 通知中心，包括铃铛入口、未读态、通知列表、详情摘要日志，以及与 `cron_reminder` 聊天消息的状态联动。

**Architecture:** 在现有 `ChatView` 上新增一个轻量通知抽屉，所有 reminder 通知状态统一交给独立的 Pinia store 管理。列表、详情、已读全部走已有后端 reminder-notifications API；WebSocket 的 `cron_reminder` 继续保留聊天消息展示，同时驱动通知 store 刷新未读计数与列表。

**Tech Stack:** Vue 3、Pinia、TypeScript、Axios、Vite、vue-tsc

---

### Task 1: 建立 Reminder Notification 数据边界

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: 定义 reminder notification 类型**

```ts
export interface ReminderSummaryLog {
  step: string
  status: string
  message: string
  timestamp?: string
}

export interface ReminderNotification {
  id: string
  job_id: string
  session_id: string | null
  task_name: string
  message: string
  delivery_status: string
  error_message: string | null
  is_read: boolean
  triggered_at: string
  read_at: string | null
  created_at: string
  updated_at: string
  summary_logs?: ReminderSummaryLog[]
}

export interface ReminderNotificationListData {
  notifications: ReminderNotification[]
  total: number
  unread_total: number
  limit: number
  offset: number
}
```

- [ ] **Step 2: 增加 reminder-notifications API 封装**

```ts
export const reminderNotificationsApi = {
  list: async (params?: { limit?: number; offset?: number }): Promise<ReminderNotificationListData> => {
    const response = await api.get<ApiResponse<ReminderNotificationListData>>('/reminder-notifications', { params })
    return response.data.data!
  },
  getDetail: async (id: string): Promise<ReminderNotification> => {
    const response = await api.get<ApiResponse<ReminderNotification>>(`/reminder-notifications/${id}`)
    return response.data.data!
  },
  markRead: async (id: string): Promise<ReminderNotification> => {
    const response = await api.post<ApiResponse<ReminderNotification>>(`/reminder-notifications/${id}/read`)
    return response.data.data!
  },
}
```

- [ ] **Step 3: 运行类型检查**

Run: `npm run build`
Expected: `vue-tsc` 不再报 reminder 类型缺失。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/index.ts
git commit -m "feat: add reminder notification api types"
```

### Task 2: 建立通知中心 Store

**Files:**
- Create: `frontend/src/stores/reminderNotifications.ts`

- [ ] **Step 1: 先写最小验证点**

```ts
// 目标行为：
// 1. loadList() 拉取列表并维护 unreadCount
// 2. selectNotification() 拉取详情并在需要时标记已读
// 3. refreshAfterRealtimeReminder() 在 websocket reminder 到达时刷新列表
```

- [ ] **Step 2: 实现独立 store**

```ts
export const useReminderNotificationsStore = defineStore('reminderNotifications', () => {
  const items = ref<ReminderNotification[]>([])
  const unreadCount = ref(0)
  const total = ref(0)
  const selectedId = ref<string | null>(null)
  const selectedDetail = ref<ReminderNotification | null>(null)
  const isDrawerOpen = ref(false)
  const loadingList = ref(false)
  const loadingDetail = ref(false)

  const loadList = async () => { /* 调 list API 并同步 unreadCount */ }
  const openDrawer = async () => { /* 打开抽屉并拉列表 */ }
  const closeDrawer = () => { /* 关闭抽屉，不清空列表 */ }
  const selectNotification = async (id: string) => { /* 拉详情并必要时 markRead */ }
  const refreshAfterRealtimeReminder = async () => { /* 保持列表与未读数同步 */ }

  return { ... }
})
```

- [ ] **Step 3: 运行构建确保 store 类型无误**

Run: `npm run build`
Expected: `frontend/src/stores/reminderNotifications.ts` 无类型错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/reminderNotifications.ts
git commit -m "feat: add reminder notifications store"
```

### Task 3: 实现通知抽屉与详情摘要日志 UI

**Files:**
- Create: `frontend/src/components/chat/ReminderNotificationsDrawer.vue`

- [ ] **Step 1: 设计组件输入输出**

```ts
const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()
```

- [ ] **Step 2: 实现列表、详情、空态、日志区块**

```vue
<template>
  <div v-if="open" class="fixed inset-0 z-40">
    <button class="absolute inset-0 bg-slate-950/60" @click="$emit('close')" />
    <aside class="absolute right-0 top-0 h-full w-full max-w-md border-l border-slate-700 bg-slate-900">
      <!-- header -->
      <!-- list -->
      <!-- detail -->
      <!-- summary_logs -->
    </aside>
  </div>
</template>
```

- [ ] **Step 3: 明确状态文案**

```ts
// delivered -> 已投递到会话
// broadcast -> 兼容广播路径
// failed -> 投递失败
// no logs -> 暂无摘要日志
```

- [ ] **Step 4: 运行构建**

Run: `npm run build`
Expected: 通知抽屉组件可以被 `ChatView` 正常引用。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ReminderNotificationsDrawer.vue
git commit -m "feat: add reminder notifications drawer"
```

### Task 4: 在聊天页接入铃铛入口与 WebSocket 联动

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: 接入通知 store 与抽屉组件**

```ts
import ReminderNotificationsDrawer from '@/components/chat/ReminderNotificationsDrawer.vue'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
```

- [ ] **Step 2: 在头部加入铃铛入口和未读 badge**

```vue
<button class="relative ...">
  <svg />
  <span v-if="unreadCount > 0" class="absolute ...">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
</button>
```

- [ ] **Step 3: 保留 `cron_reminder` 聊天消息并同步刷新通知状态**

```ts
} else if (data.type === 'cron_reminder') {
  // 继续 push system message
  await reminderNotificationsStore.refreshAfterRealtimeReminder()
}
```

- [ ] **Step 4: 在页面初始化时预拉通知列表**

```ts
onMounted(async () => {
  await Promise.all([
    chatStore.initIfEmpty(),
    reminderNotificationsStore.loadList(),
  ])
})
```

- [ ] **Step 5: 运行构建**

Run: `npm run build`
Expected: 聊天页可通过铃铛打开通知抽屉，且 build 通过。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ChatView.vue
git commit -m "feat: add reminder notification entry to chat view"
```

### Task 5: 增加 Task 6.2 的最小前端验证用例

**Files:**
- Create: `frontend/src/stores/reminderNotifications.spec.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: 引入最小测试运行能力**

```json
{
  "scripts": {
    "test:unit": "vitest run"
  },
  "devDependencies": {
    "vitest": "...",
    "@vue/test-utils": "...",
    "jsdom": "..."
  }
}
```

- [ ] **Step 2: 为通知 store/入口行为写聚焦测试**

```ts
it('loads unread count and marks detail as read', async () => {
  // mock api
  // assert unreadCount
  // assert markRead after selectNotification
})
```

- [ ] **Step 3: 运行测试**

Run: `npm run test:unit`
Expected: 至少覆盖铃铛未读态与详情已读联动。

- [ ] **Step 4: 再次运行构建**

Run: `npm run build`
Expected: build 仍然通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src/stores/reminderNotifications.spec.ts
git commit -m "test: cover reminder notifications store"
```
