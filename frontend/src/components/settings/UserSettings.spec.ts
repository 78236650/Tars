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
})
