import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import ReminderBellButton from './ReminderBellButton.vue'
import ReminderNotificationsDrawer from './ReminderNotificationsDrawer.vue'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'

describe('reminder notifications UI', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders bell badge and emits open event', async () => {
    const wrapper = mount(ReminderBellButton, {
      props: {
        unreadCount: 3,
      },
    })

    expect(wrapper.text()).toContain('3')
    await wrapper.trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('renders notification detail summary and broadcast fallback text', () => {
    const store = useReminderNotificationsStore()
    store.items = [
      {
        id: 'notification-1',
        job_id: 'job-1',
        session_id: null,
        task_name: '站起来活动',
        message: '起来活动一下',
        delivery_status: 'broadcast',
        error_message: '缺少 session_id，回退广播路径',
        is_read: false,
        triggered_at: '2026-05-15T10:00:00+08:00',
        read_at: null,
        created_at: '2026-05-15T10:00:00+08:00',
        updated_at: '2026-05-15T10:00:00+08:00',
      },
    ]
    store.unreadCount = 1
    store.selectedId = 'notification-1'
    store.selectedDetail = {
      ...store.items[0],
      summary_logs: [
        { step: 'scheduler_matched', status: 'ok', message: '调度命中' },
        { step: 'delivery_result', status: 'broadcast', message: '通过 broadcast 投递通知' },
      ],
    }

    const wrapper = mount(ReminderNotificationsDrawer, {
      props: {
        open: true,
      },
    })

    expect(wrapper.text()).toContain('提醒通知')
    expect(wrapper.text()).toContain('站起来活动')
    expect(wrapper.text()).toContain('起来活动一下')
    expect(wrapper.text()).toContain('兼容广播路径')
    expect(wrapper.text()).toContain('摘要日志')
    expect(wrapper.text()).toContain('调度命中')
    expect(wrapper.text()).toContain('通过 broadcast 投递通知')
  })
})
