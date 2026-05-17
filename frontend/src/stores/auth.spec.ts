import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { authApi } from '@/api'

vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}))

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('persists api key after account login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      api_key: 'key-123',
      user: {
        id: 'u1',
        username: 'alice',
        email: 'alice@example.com',
        role: 'user',
        created_at: '2026-05-17T09:00:00Z',
      },
    })

    const store = useAuthStore()
    const ok = await store.loginWithCredentials('alice@example.com', 'S3curePass!')

    expect(ok).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('apiKey')).toBe('key-123')
  })
})
