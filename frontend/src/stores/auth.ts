import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import type { User } from '@/types'

const API_KEY_STORAGE_KEY = 'apiKey'
export const ACCESS_TOKEN_STORAGE_KEY = 'tars_access_token'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)
  const apiKey = ref('')
  const accessToken = ref('')

  const setApiKey = (key: string) => {
    apiKey.value = key
    localStorage.setItem(API_KEY_STORAGE_KEY, key)
  }

  const clearApiKey = () => {
    apiKey.value = ''
    localStorage.removeItem(API_KEY_STORAGE_KEY)
  }

  const setAccessToken = (token: string) => {
    accessToken.value = token
    localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
  }

  const clearAccessToken = () => {
    accessToken.value = ''
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  }

  const getAccessToken = (): string => {
    return accessToken.value || localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) || ''
  }

  const login = async (key: string) => {
    try {
      setApiKey(key)
      const response = await authApi.getCurrentUser(key)
      user.value = response
      isAuthenticated.value = true
      localStorage.setItem('auth_user', JSON.stringify(response))
      return true
    } catch {
      clearApiKey()
      return false
    }
  }

  const loginWithCredentials = async (identifier: string, password: string) => {
    try {
      const response = await authApi.login(identifier, password)
      if (response.access_token) {
        setAccessToken(response.access_token)
      }
      setApiKey(response.api_key)
      user.value = response.user
      isAuthenticated.value = true
      localStorage.setItem('auth_user', JSON.stringify(response.user))
      return true
    } catch {
      logout()
      return false
    }
  }

  const logout = async () => {
    const token = getAccessToken()
    if (token) {
      try {
        await authApi.logout()
      } catch {
        /* clear local state even if revoke fails */
      }
    }
    user.value = null
    isAuthenticated.value = false
    clearAccessToken()
    clearApiKey()
    localStorage.removeItem('auth_user')
    // 强制跳转到登录页
    window.location.href = '/login'
  }

  const initAuth = async () => {
    const savedToken = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
    const savedKey = localStorage.getItem(API_KEY_STORAGE_KEY)
    if (!savedKey && !savedToken) {
      return
    }

    if (savedToken) {
      accessToken.value = savedToken
    }

    try {
      const response = await authApi.getCurrentUser(savedKey || undefined)
      if (savedKey) {
        apiKey.value = savedKey
      }
      user.value = response
      isAuthenticated.value = true
      localStorage.setItem('auth_user', JSON.stringify(response))
    } catch {
      logout()
    }
  }

  /** 用本地缓存快速恢复登录态，避免整页刷新时长时间白屏 */
  const restoreFromCache = (): boolean => {
    const savedToken = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
    const savedKey = localStorage.getItem(API_KEY_STORAGE_KEY)
    const cachedUser = localStorage.getItem('auth_user')
    if ((!savedKey && !savedToken) || !cachedUser) return false
    try {
      if (savedToken) accessToken.value = savedToken
      if (savedKey) apiKey.value = savedKey
      user.value = JSON.parse(cachedUser) as User
      isAuthenticated.value = true
      return true
    } catch {
      return false
    }
  }

  return {
    user,
    isAuthenticated,
    apiKey,
    accessToken,
    setApiKey,
    clearApiKey,
    setAccessToken,
    clearAccessToken,
    getAccessToken,
    login,
    loginWithCredentials,
    logout,
    initAuth,
    restoreFromCache,
  }
})
