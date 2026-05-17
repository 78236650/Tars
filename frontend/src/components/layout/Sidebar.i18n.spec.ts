import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import Sidebar from './Sidebar.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useI18n } from '@/i18n'

describe('Sidebar i18n', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useI18n().setLocale('zh')
  })

  it('switches sidebar helper text, search placeholder, and session groups with locale', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/memory', component: { template: '<div />' } },
        { path: '/settings', component: { template: '<div />' } },
        { path: '/models', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const settingsStore = useSettingsStore()
    settingsStore.currentModel = 'qwen3:8b'
    settingsStore.currentProvider = 'ollama'
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

    const wrapper = mount(Sidebar, {
      global: {
        plugins: [router],
        stubs: {
          Teleport: true,
        },
      },
    })

    expect(wrapper.text()).toContain('聊天')
    expect(wrapper.text()).toContain('AI 工作助理')
    expect(wrapper.text()).toContain('今天')
    expect(wrapper.text()).toContain('昨天')
    expect(wrapper.text()).toContain('更早')
    expect(wrapper.find('input[type="text"]').attributes('placeholder')).toBe('搜索会话...')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('Chat')
    expect(wrapper.text()).toContain('AI Workspace Assistant')
    expect(wrapper.text()).toContain('Today')
    expect(wrapper.text()).toContain('Yesterday')
    expect(wrapper.text()).toContain('Earlier')
    expect(wrapper.find('input[type="text"]').attributes('placeholder')).toBe('Search sessions...')
  })

  it('localizes delete failure toast message', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/memory', component: { template: '<div />' } },
        { path: '/settings', component: { template: '<div />' } },
        { path: '/models', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const settingsStore = useSettingsStore()
    settingsStore.currentModel = 'qwen3:8b'
    settingsStore.currentProvider = 'ollama'
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
    ]
    chatStore.deleteSession = vi.fn(async () => {
      throw new Error('boom')
    })

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    const wrapper = mount(Sidebar, {
      global: {
        plugins: [router],
        stubs: {
          Teleport: true,
        },
      },
    })

    await wrapper.find('.group .cursor-pointer').trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('删除失败')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    await wrapper.find('.group .cursor-pointer').trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('Delete failed')
    confirmSpy.mockRestore()
  })
})
