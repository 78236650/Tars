import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import type { User } from '@/types'

const API_KEY_STORAGE_KEY = 'apiKey'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)
  const apiKey = ref('')

  const setApiKey = (key: string) => {
    apiKey.value = key
    localStorage.setItem(API_KEY_STORAGE_KEY, key)
  }

  const clearApiKey = () => {
    apiKey.value = ''
    localStorage.removeItem(API_KEY_STORAGE_KEY)
  }

  const login = async (key: string) => {
    try {
      setApiKey(key)
      const response = await authApi.getCurrentUser(key)
      user.value = response
      isAuthenticated.value = true
      return true
    } catch {
      clearApiKey()
      return false
    }
  }

  const loginWithCredentials = async (identifier: string, password: string) => {
    try {
      const response = await authApi.login(identifier, password)
      setApiKey(response.api_key)
      user.value = response.user
      isAuthenticated.value = true
      return true
    } catch {
      logout()
      return false
    }
  }

  const logout = () => {
    user.value = null
    isAuthenticated.value = false
    clearApiKey()
  }

  const initAuth = async () => {
    const savedKey = localStorage.getItem(API_KEY_STORAGE_KEY)
    if (!savedKey) {
      return
    }

    try {
      const response = await authApi.getCurrentUser(savedKey)
      apiKey.value = savedKey
      user.value = response
      isAuthenticated.value = true
    } catch {
      logout()
    }
  }

  return {
    user,
    isAuthenticated,
    apiKey,
    setApiKey,
    clearApiKey,
    login,
    loginWithCredentials,
    logout,
    initAuth
  }
})
