import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import UserSettings from './UserSettings.vue'

vi.mock('@/api', () => ({
  authApi: {
    getUsers: vi.fn(),
    createUser: vi.fn(),
    deleteUser: vi.fn(),
  },
}))

describe('UserSettings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.user = {
      id: 'admin-1',
      username: 'admin',
      email: 'admin@example.com',
      role: 'admin',
      created_at: '2026-05-16T10:00:00Z',
    }

    vi.mocked(authApi.getUsers).mockResolvedValue({
      users: [],
      total: 0,
    })
  })

  it('uses the shared dialog surface for the create user flow', async () => {
    const wrapper = mount(UserSettings)

    await wrapper.find('button').trigger('click')

    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
    expect(wrapper.html()).toContain('rounded-[28px]')
  })

  it('shows an initial password field in the create user dialog', async () => {
    const wrapper = mount(UserSettings)

    await wrapper.find('button').trigger('click')

    expect(wrapper.html()).toContain('type="password"')
  })

  it('passes the initial password when creating a user', async () => {
    vi.mocked(authApi.createUser).mockResolvedValue({
      success: true,
      message: 'ok',
    })

    const wrapper = mount(UserSettings)

    await wrapper.find('button').trigger('click')
    await wrapper.find('input').setValue('alice')
    await wrapper.find('input[type="email"]').setValue('alice@example.com')
    await wrapper.find('input[type="password"]').setValue('TempPass123!')
    await wrapper.find('select').setValue('admin')
    await wrapper.findAll('button').at(-1)?.trigger('click')

    expect(authApi.createUser).toHaveBeenCalledWith('alice', 'alice@example.com', 'TempPass123!', 'admin')
  })
})
