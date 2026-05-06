import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi } from '@/api'
import type { ChatSession } from '@/types'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)

  const loadSessions = async () => {
    sessions.value = await sessionsApi.list()
  }

  const createSession = async (): Promise<ChatSession> => {
    const s = await sessionsApi.create()
    sessions.value.unshift(s)
    currentSessionId.value = s.id
    return s
  }

  const switchSession = (id: string) => {
    currentSessionId.value = id
  }

  const deleteSession = async (id: string) => {
    await sessionsApi.delete(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value[0]?.id ?? null
    }
  }

  const updateTitle = async (id: string, title: string) => {
    await sessionsApi.updateTitle(id, title)
    const target = sessions.value.find(s => s.id === id)
    if (target) target.title = title
  }

  const initIfEmpty = async () => {
    await loadSessions()
    if (sessions.value.length === 0) {
      await createSession()
    } else if (!currentSessionId.value) {
      currentSessionId.value = sessions.value[0].id
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
  }
})
