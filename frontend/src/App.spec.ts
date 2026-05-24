import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    initAuth: vi.fn().mockResolvedValue(undefined),
    isAuthenticated: true,
    restoreFromCache: vi.fn().mockReturnValue(true),
  }),
}))

const initSettings = vi.fn().mockResolvedValue(undefined)
const loadModels = vi.fn().mockResolvedValue(undefined)

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    loadModels,
    initSettings,
  }),
}))

describe('App shell gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders route component without DesktopShell when shell meta is false', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/login',
          component: { template: '<div data-test="login-page">Login Page</div>' },
          meta: { shell: false },
        },
      ],
    })
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: {
          DesktopShell: { template: '<div data-test="desktop-shell"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-test="login-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="desktop-shell"]').exists()).toBe(false)
  })

  it('wraps route component in DesktopShell by default', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div data-test="home-page">Home Page</div>' },
          meta: { shell: true },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: {
          DesktopShell: { template: '<div data-test="desktop-shell"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-test="home-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="desktop-shell"]').exists()).toBe(true)
  })

  it('calls initSettings when authenticated after auth init', async () => {
    initSettings.mockClear()
    loadModels.mockClear()

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div>Home</div>' },
        },
      ],
    })
    await router.push('/')
    await router.isReady()

    mount(App, {
      global: {
        plugins: [router],
        stubs: { DesktopShell: { template: '<div><slot /></div>' } },
      },
    })

    await flushPromises()

    expect(initSettings).toHaveBeenCalled()
    expect(loadModels).not.toHaveBeenCalled()
  })
})
