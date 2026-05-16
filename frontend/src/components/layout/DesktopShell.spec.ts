import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, expect, it, beforeEach } from 'vitest'
import DesktopShell from './DesktopShell.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWsStore } from '@/stores/wsStore'

describe('DesktopShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders route metadata in header', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/memory',
          component: { template: '<div class="memory-page">Memory Page</div>' },
          meta: {
            desktopTitle: '记忆工作台',
            desktopSubtitle: '统一查看与管理记忆',
          },
        },
      ],
    })
    await router.push('/memory')
    await router.isReady()

    const settingsStore = useSettingsStore()
    settingsStore.currentModel = 'qwen3:8b'
    settingsStore.currentProvider = 'ollama'

    const wsStore = useWsStore()
    wsStore.isConnected = true

    const wrapper = mount(DesktopShell, {
      global: {
        plugins: [router],
        stubs: {
          LeftPanel: { template: '<div data-test="left-panel">Left</div>' },
          RightPanel: { template: '<div data-test="right-panel">Right</div>' },
          ReminderBellButton: { template: '<button data-test="reminder-bell">Bell</button>' },
          ReminderNotificationsDrawer: { template: '<div data-test="reminder-drawer"></div>' },
        },
      },
      slots: {
        default: '<div class="slot-body">Main Content</div>',
      },
    })

    expect(wrapper.text()).toContain('记忆工作台')
    expect(wrapper.text()).toContain('统一查看与管理记忆')
    expect(wrapper.text()).toContain('qwen3:8b')
    expect(wrapper.find('.slot-body').exists()).toBe(true)
  })

  it('renders three-column layout with LeftPanel and RightPanel', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div class="chat-page">Chat Page</div>' },
          meta: {
            desktopTitle: '聊天工作台',
            desktopSubtitle: '对话工作区',
          },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(DesktopShell, {
      global: {
        plugins: [router],
        stubs: {
          LeftPanel: { template: '<div data-test="left-panel">Left</div>' },
          RightPanel: { template: '<div data-test="right-panel">Right</div>' },
          ReminderBellButton: { template: '<button data-test="reminder-bell">Bell</button>' },
          ReminderNotificationsDrawer: { template: '<div data-test="reminder-drawer"></div>' },
        },
      },
      slots: {
        default: '<div class="slot-body">Main Content</div>',
      },
    })

    expect(wrapper.find('[data-test="left-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="right-panel"]').exists()).toBe(true)
    expect(wrapper.find('.slot-body').exists()).toBe(true)
    expect(wrapper.find('main').exists()).toBe(true)
  })

  it('displays model info in header', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div />' },
          meta: {
            desktopTitle: '聊天',
            desktopSubtitle: '对话',
          },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const settingsStore = useSettingsStore()
    settingsStore.currentModel = 'qwen3:8b'
    settingsStore.currentProvider = 'ollama'

    const wrapper = mount(DesktopShell, {
      global: {
        plugins: [router],
        stubs: {
          LeftPanel: { template: '<div />' },
          RightPanel: { template: '<div />' },
          ReminderBellButton: { template: '<button />' },
          ReminderNotificationsDrawer: { template: '<div />' },
        },
      },
      slots: { default: '<div />' },
    })

    expect(wrapper.text()).toContain('qwen3:8b')
  })

  it('shows connection status indicator', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div />' },
          meta: {
            desktopTitle: '聊天',
            desktopSubtitle: '对话',
          },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wsStore = useWsStore()
    wsStore.isConnected = true

    const wrapper = mount(DesktopShell, {
      global: {
        plugins: [router],
        stubs: {
          LeftPanel: { template: '<div />' },
          RightPanel: { template: '<div />' },
          ReminderBellButton: { template: '<button />' },
          ReminderNotificationsDrawer: { template: '<div />' },
        },
      },
      slots: { default: '<div />' },
    })

    const connectedIndicator = wrapper.find('.bg-emerald-400')
    expect(connectedIndicator.exists()).toBe(true)
  })

  it('renders reminder bell button', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div />' },
          meta: {
            desktopTitle: '聊天',
            desktopSubtitle: '对话',
          },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(DesktopShell, {
      global: {
        plugins: [router],
        stubs: {
          LeftPanel: { template: '<div />' },
          RightPanel: { template: '<div />' },
          ReminderBellButton: { template: '<button data-test="reminder-bell">Bell</button>' },
          ReminderNotificationsDrawer: { template: '<div />' },
        },
      },
      slots: { default: '<div />' },
    })

    expect(wrapper.find('[data-test="reminder-bell"]').exists()).toBe(true)
  })
})
