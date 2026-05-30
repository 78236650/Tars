import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ACCESS_TOKEN_STORAGE_KEY, useAuthStore } from './auth'
import { authApi } from '@/api'

vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
    logout: vi.fn(),
  },
}))

const mockUser = {
  id: 'u1',
  username: 'alice',
  email: 'alice@example.com',
  role: 'user',
  created_at: '2026-05-17T09:00:00Z',
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('persists api key after account login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'jwt-abc',
      api_key: 'key-123',
      user: mockUser,
    })

    const store = useAuthStore()
    const ok = await store.loginWithCredentials('alice@example.com', 'S3curePass!')

    expect(ok).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('apiKey')).toBe('key-123')
  })

  it('persists access token after account login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'jwt-abc',
      api_key: 'key-123',
      user: mockUser,
    })

    const store = useAuthStore()
    await store.loginWithCredentials('alice@example.com', 'S3curePass!')

    expect(localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBe('jwt-abc')
    expect(store.getAccessToken()).toBe('jwt-abc')
  })

  it('clears access token on logout', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'jwt-abc',
      api_key: 'key-123',
      user: mockUser,
    })

    const store = useAuthStore()
    await store.loginWithCredentials('alice@example.com', 'S3curePass!')
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    await store.logout()

    expect(localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
    expect(store.getAccessToken()).toBe('')
  })

  it('still works when login response has no access_token', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      api_key: 'key-only',
      user: mockUser,
    })

    const store = useAuthStore()
    const ok = await store.loginWithCredentials('alice@example.com', 'S3curePass!')

    expect(ok).toBe(true)
    expect(localStorage.getItem('apiKey')).toBe('key-only')
    expect(localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)).toBeNull()
  })
})
