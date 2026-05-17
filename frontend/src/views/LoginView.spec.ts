import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from './LoginView.vue'
import { useAuthStore } from '@/stores/auth'

const pushMock = vi.fn()

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')

  return {
    ...actual,
    useRouter: () => ({
      push: pushMock,
    }),
  }
})

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pushMock.mockReset()
  })

  it('renders the brand panel and login card', () => {
    const wrapper = mount(LoginView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('TARS')
    expect(wrapper.text()).toContain('登录并进入')
    expect(wrapper.text()).toContain('加入工作区')
  })

  it('expands join workspace panel from the login card', async () => {
    const wrapper = mount(LoginView)

    const joinButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('加入工作区'))

    expect(joinButton).toBeDefined()

    await joinButton!.trigger('click')

    expect(wrapper.text()).toContain('邀请码')
  })

  it('shows a card error when credentials are rejected', async () => {
    const store = useAuthStore()
    store.loginWithCredentials = vi.fn().mockResolvedValue(false)

    const wrapper = mount(LoginView)

    await wrapper.find('input').setValue('alice@example.com')
    await wrapper.find('input[type="password"]').setValue('wrong-pass')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('登录并进入'))!
      .trigger('click')
    await flushPromises()

    expect(store.loginWithCredentials).toHaveBeenCalledWith('alice@example.com', 'wrong-pass')
    expect(wrapper.text()).toContain('用户名或密码错误')
  })

  it('calls the auth store and redirects after successful submit', async () => {
    const store = useAuthStore()
    store.loginWithCredentials = vi.fn().mockResolvedValue(true)

    const wrapper = mount(LoginView)

    await wrapper.find('input').setValue('alice@example.com')
    await wrapper.find('input[type="password"]').setValue('S3curePass!')
    await wrapper.findAll('input')[2].setValue('workspace-a')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('登录并进入'))!
      .trigger('click')
    await flushPromises()

    expect(store.loginWithCredentials).toHaveBeenCalledWith('alice@example.com', 'S3curePass!')
    expect(pushMock).toHaveBeenCalledWith('/?workspace=workspace-a')
  })
})
