import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from './index'
import { useAuthStore } from '@/stores/auth'

describe('router auth guards', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()

    authStore.$patch({
      isAuthenticated: false,
      user: null,
      apiKey: '',
    })

    await router.push('/')
    await router.push('/login').catch(() => undefined)
  })

  it('redirects anonymous users to /login for protected routes', async () => {
    await router.push('/memory')

    expect(router.currentRoute.value.fullPath).toBe('/login')
  })

  it('redirects authenticated users away from /login', async () => {
    const authStore = useAuthStore()

    authStore.$patch({
      isAuthenticated: true,
      user: {
        id: 'u1',
        username: 'alice',
        email: 'alice@example.com',
        role: 'user',
        created_at: '2026-05-17T09:00:00Z',
      },
      apiKey: 'key-123',
    })

    await router.push('/')
    await router.push('/login')

    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
