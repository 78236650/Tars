import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi } from '@/api'
import type { ChatSession } from '@/types'
import { useAuthStore } from '@/stores/auth'

const SESSION_STORAGE_KEY = 'tars_current_session'

function scopedSessionKey(userId?: string | null): string {
  return `${SESSION_STORAGE_KEY}:${userId || 'default'}`
}

function readStoredSessionId(userId?: string | null): string | null {
  const scopedKey = scopedSessionKey(userId)
  const scoped = localStorage.getItem(scopedKey)
  if (scoped) return scoped
  const legacy = localStorage.getItem(SESSION_STORAGE_KEY)
  if (legacy && userId) {
    localStorage.setItem(scopedKey, legacy)
    localStorage.removeItem(SESSION_STORAGE_KEY)
    return legacy
  }
  return legacy
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)

  const persistSessionId = (id: string | null) => {
    const authStore = useAuthStore()
    const key = scopedSessionKey(authStore.user?.id)
    if (id) {
      localStorage.setItem(key, id)
    } else {
      localStorage.removeItem(key)
    }
  }

  const restoreSessionId = () => {
    const authStore = useAuthStore()
    currentSessionId.value = readStoredSessionId(authStore.user?.id)
  }

  const loadSessions = async () => {
    sessions.value = await sessionsApi.list()
  }

  const createSession = async (): Promise<ChatSession> => {
    const s = await sessionsApi.create()
    sessions.value.unshift(s)
    currentSessionId.value = s.id
    persistSessionId(s.id)
    return s
  }

  const switchSession = (id: string) => {
    currentSessionId.value = id
    persistSessionId(id)
  }

  const deleteSession = async (id: string) => {
    await sessionsApi.delete(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      const nextId = sessions.value[0]?.id ?? null
      currentSessionId.value = nextId
      persistSessionId(nextId)
    }
  }

  const updateTitle = async (id: string, title: string) => {
    await sessionsApi.updateTitle(id, title)
    const target = sessions.value.find(s => s.id === id)
    if (target) target.title = title
  }

  const initIfEmpty = async () => {
    restoreSessionId()
    await loadSessions()
    if (sessions.value.length === 0) {
      await createSession()
      return
    }
    const stored = currentSessionId.value
    if (!stored || !sessions.value.find(s => s.id === stored)) {
      switchSession(sessions.value[0].id)
    }
  }

  return {
    sessions,
    currentSessionId,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
    updateTitle,
    initIfEmpty,
    restoreSessionId,
  }
})
