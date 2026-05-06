import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)
  const apiKey = ref('')

  const setApiKey = (key: string) => {
    apiKey.value = key
    localStorage.setItem('apiKey', key)
  }

  const clearApiKey = () => {
    apiKey.value = ''
    localStorage.removeItem('apiKey')
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

  const logout = () => {
    user.value = null
    isAuthenticated.value = false
    clearApiKey()
  }

  const initAuth = async () => {
    const savedKey = localStorage.getItem('apiKey')
    if (savedKey) {
      try {
        const response = await authApi.getCurrentUser(savedKey)
        user.value = response
        isAuthenticated.value = true
        apiKey.value = savedKey
      } catch {
        clearApiKey()
      }
    }
  }

  return {
    user,
    isAuthenticated,
    apiKey,
    setApiKey,
    clearApiKey,
    login,
    logout,
    initAuth
  }
})