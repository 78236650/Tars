import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, expect, it, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import DesktopShell from './DesktopShell.vue'
import LeftPanel from './LeftPanel.vue'
import { useI18n } from '@/i18n'

describe('DesktopShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useI18n().setLocale('zh')
  })

  it('renders desktop title and subtitle from i18n route keys', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/models',
          component: { template: '<div />' },
          meta: {
            desktopTitleKey: 'desktop.models.title',
            desktopSubtitleKey: 'desktop.models.subtitle',
          },
        },
      ],
    })
    await router.push('/models')
    await router.isReady()

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

    expect(wrapper.text()).toContain('模型中心')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('Model Center')
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

  it('renders reminder bell button in left sidebar', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div />' },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(LeftPanel, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('[data-test="sidebar-reminder-bell"]').exists()).toBe(true)
  })
})
