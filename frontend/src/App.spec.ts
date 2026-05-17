import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    initAuth: vi.fn().mockResolvedValue(undefined),
  }),
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    loadModels: vi.fn().mockResolvedValue(undefined),
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
})
