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
  rolesApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'developer', name: '开发者', description: '', allowed_tools: [], allowed_modules: [], max_concurrent: 1 },
    ]),
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

  it('shows the assigned role template in the role column', async () => {
    vi.mocked(authApi.getUsers).mockResolvedValue({
      users: [
        {
          id: 'user-1',
          username: 'bob',
          email: 'bob@example.com',
          role: 'user',
          role_template_id: 'developer',
          created_at: '2026-05-16T10:00:00Z',
        },
      ],
      total: 1,
    })

    const wrapper = mount(UserSettings)
    await vi.waitFor(() => expect(wrapper.text()).toContain('开发者'))

    expect(wrapper.text()).not.toContain('userSettings.roles.user')
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
    await vi.waitFor(() => expect(wrapper.find('select option').exists()).toBe(true))
    await wrapper.find('select').setValue('developer')
    await wrapper.findAll('button').at(-1)?.trigger('click')

    expect(authApi.createUser).toHaveBeenCalledWith('alice', 'alice@example.com', 'TempPass123!', 'developer')
  })
})
