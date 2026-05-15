import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useReminderNotificationsStore } from './reminderNotifications'
import { reminderNotificationsApi } from '@/api'
import type { ReminderNotification } from '@/types'

vi.mock('@/api', () => ({
  reminderNotificationsApi: {
    list: vi.fn(),
    getDetail: vi.fn(),
    markRead: vi.fn(),
  },
}))

const baseNotification: ReminderNotification = {
  id: 'notification-1',
  job_id: 'job-1',
  session_id: 'session-1',
  task_name: '喝水提醒',
  message: '记得喝水',
  delivery_status: 'delivered',
  error_message: null,
  is_read: false,
  triggered_at: '2026-05-15T10:00:00+08:00',
  read_at: null,
  created_at: '2026-05-15T10:00:00+08:00',
  updated_at: '2026-05-15T10:00:00+08:00',
  summary_logs: [
    { step: 'scheduler_matched', status: 'ok', message: '调度命中' },
  ],
}

describe('useReminderNotificationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads list and keeps unread count in sync', async () => {
    vi.mocked(reminderNotificationsApi.list).mockResolvedValue({
      notifications: [
        baseNotification,
        { ...baseNotification, id: 'notification-2', is_read: true },
      ],
      total: 2,
      unread_total: 1,
      limit: 20,
      offset: 0,
    })

    const store = useReminderNotificationsStore()
    await store.loadList()

    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
    expect(store.unreadCount).toBe(1)
    expect(store.listLoaded).toBe(true)
  })

  it('loads detail and marks unread notification as read', async () => {
    vi.mocked(reminderNotificationsApi.list).mockResolvedValue({
      notifications: [baseNotification],
      total: 1,
      unread_total: 1,
      limit: 20,
      offset: 0,
    })
    vi.mocked(reminderNotificationsApi.getDetail).mockResolvedValue(baseNotification)
    vi.mocked(reminderNotificationsApi.markRead).mockResolvedValue({
      ...baseNotification,
      is_read: true,
      read_at: '2026-05-15T10:01:00+08:00',
    })

    const store = useReminderNotificationsStore()
    await store.loadList()
    await store.selectNotification(baseNotification.id)

    expect(reminderNotificationsApi.getDetail).toHaveBeenCalledWith(baseNotification.id)
    expect(reminderNotificationsApi.markRead).toHaveBeenCalledWith(baseNotification.id)
    expect(store.unreadCount).toBe(0)
    expect(store.selectedDetail?.is_read).toBe(true)
    expect(store.items[0].is_read).toBe(true)
  })
})
