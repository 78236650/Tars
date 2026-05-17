import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import LeftPanel from './LeftPanel.vue'
import RightPanel from './RightPanel.vue'
import { useChatStore } from '@/stores/chat'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useSettingsStore } from '@/stores/settings'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'

const buildRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/memory', component: { template: '<div />' } },
      { path: '/settings', component: { template: '<div />' } },
      { path: '/models', component: { template: '<div />' } },
      { path: '/tools', component: { template: '<div />' } },
      { path: '/bi', component: { template: '<div />' } },
      { path: '/knowledge', component: { template: '<div />' } },
      { path: '/meeting', component: { template: '<div />' } },
    ],
  })

describe('layout panels i18n', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useI18n().setLocale('zh')

    const settingsStore = useSettingsStore()
    settingsStore.currentModel = 'qwen3:8b'
    settingsStore.currentProvider = 'ollama'
    settingsStore.ollamaModels = ['qwen3:8b']
    settingsStore.endpoints = []
    settingsStore.loadModels = async () => {}

    const chatStore = useChatStore()
    chatStore.loadSessions = async () => {}
    chatStore.currentSessionId = 'session-today'
    chatStore.sessions = [
      {
        id: 'session-today',
        title: '今天的会话',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 'session-yesterday',
        title: '昨天的会话',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        updated_at: new Date(Date.now() - 86400000).toISOString(),
      },
      {
        id: 'session-older',
        title: '更早的会话',
        created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
        updated_at: new Date(Date.now() - 86400000 * 3).toISOString(),
      },
    ]

    const wsStore = useWsStore()
    wsStore.isConnected = true

    const reminderStore = useReminderNotificationsStore()
    reminderStore.unreadCount = 2
  })

  it('switches left and right panel user-facing copy with locale', async () => {
    const router = buildRouter()
    await router.push('/')
    await router.isReady()

    const leftWrapper = mount(LeftPanel, {
      global: {
        plugins: [router],
      },
    })
    const rightWrapper = mount(RightPanel, {
      global: {
        plugins: [router],
      },
    })

    expect(leftWrapper.text()).toContain('聊天')
    expect(
      leftWrapper.findAll('button').find((button) => button.text() === 'EN')?.attributes('title'),
    ).toBe('切换到英文')
    expect(leftWrapper.find('button[aria-label="模型配置"]').attributes('title')).toBe('模型配置')

    expect(rightWrapper.text()).toContain('收起')
    expect(rightWrapper.text()).toContain('今天')
    expect(rightWrapper.text()).toContain('昨天')
    expect(rightWrapper.text()).toContain('更早')
    expect(rightWrapper.text()).toContain('快捷操作')
    expect(rightWrapper.text()).toContain('复制')
    expect(rightWrapper.text()).toContain('导出')
    expect(rightWrapper.text()).toContain('记忆')
    expect(rightWrapper.text()).toContain('清空')
    expect(rightWrapper.text()).toContain('状态概览')
    expect(rightWrapper.text()).toContain('会话数')
    expect(rightWrapper.text()).toContain('连接状态')
    expect(rightWrapper.text()).toContain('未读提醒')
    expect(rightWrapper.find('input[type="text"]').attributes('placeholder')).toBe('搜索会话...')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(leftWrapper.text()).toContain('Chat')
    expect(
      leftWrapper.findAll('button').find((button) => button.text() === '中')?.attributes('title'),
    ).toBe('Switch to Chinese')
    expect(leftWrapper.find('button[aria-label="Model settings"]').attributes('title')).toBe('Model settings')

    expect(rightWrapper.text()).toContain('Collapse')
    expect(rightWrapper.text()).toContain('Today')
    expect(rightWrapper.text()).toContain('Yesterday')
    expect(rightWrapper.text()).toContain('Earlier')
    expect(rightWrapper.text()).toContain('Quick Actions')
    expect(rightWrapper.text()).toContain('Copy')
    expect(rightWrapper.text()).toContain('Export')
    expect(rightWrapper.text()).toContain('Memory')
    expect(rightWrapper.text()).toContain('Clear')
    expect(rightWrapper.text()).toContain('Status Overview')
    expect(rightWrapper.text()).toContain('Sessions')
    expect(rightWrapper.text()).toContain('Connection')
    expect(rightWrapper.text()).toContain('Unread')
    expect(rightWrapper.find('input[type="text"]').attributes('placeholder')).toBe('Search sessions...')
  })
})
