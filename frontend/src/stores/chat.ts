import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi } from '@/api'
import type { ChatSession } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { createChatMessageState, type ChatMessageItem } from '@/stores/chatRealtime'

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
  const externalApprovalCount = ref(0)
  const externalHandoffCount = ref(0)

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
    void messageState.loadSessionMessages(id)
  }

  const messageState = createChatMessageState(() => currentSessionId.value, switchSession)

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

  const appendUserMessage = (sessionId: string, message: ChatMessageItem) => {
    messageState.appendMessage(sessionId, message)
  }

  const clearActiveSkills = (sessionId: string) => {
    messageState.setActiveSkills(sessionId, [])
  }

  const noteExternalApproval = () => {
    externalApprovalCount.value += 1
  }

  const noteExternalHandoff = () => {
    externalHandoffCount.value += 1
  }

  const clearExternalNotifications = () => {
    externalApprovalCount.value = 0
    externalHandoffCount.value = 0
  }

  return {
    sessions,
    currentSessionId,
    externalApprovalCount,
    externalHandoffCount,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
    updateTitle,
    initIfEmpty,
    restoreSessionId,
    currentMessages: messageState.currentMessages,
    currentActiveSkills: messageState.currentActiveSkills,
    messagesLoading: messageState.messagesLoading,
    loadSessionMessages: messageState.loadSessionMessages,
    initChatRealtime: messageState.initChatRealtime,
    appendUserMessage,
    appendMessage: messageState.appendMessage,
    clearActiveSkills,
    noteExternalApproval,
    noteExternalHandoff,
    clearExternalNotifications,
  }
})
