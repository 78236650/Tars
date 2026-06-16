import { computed, ref } from 'vue'
import { sessionsApi } from '@/api'
import { useI18n } from '@/i18n'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useWsStore } from '@/stores/wsStore'

export interface ChatMessageToolCall {
  id?: string
  tool: string
  parameters?: Record<string, unknown>
  success?: boolean
  output?: string
  error?: string
  duration?: number
  metadata?: Record<string, unknown>
  timestamp: string
}

export interface ChatMessageItem {
  id: string
  role: string
  content: string
  timestamp: string
  attachments?: any[]
  toolCalls?: ChatMessageToolCall[]
  thinking?: {
    isActive: boolean
    steps: Array<{
      id: string
      step: string
      title: string
      detail?: string
      timestamp: string
    }>
  }
  task?: any
  plan?: any
  planSteps?: any[]
}

const MESSAGE_CACHE_PREFIX = 'tars_chat_messages:'

function messageCacheKey(sessionId: string) {
  return `${MESSAGE_CACHE_PREFIX}${sessionId}`
}

function persistMessageCache(sessionId: string, msgs: ChatMessageItem[]) {
  try {
    sessionStorage.setItem(messageCacheKey(sessionId), JSON.stringify(msgs))
  } catch {
    /* ignore quota errors */
  }
}

function readMessageCache(sessionId: string): ChatMessageItem[] | null {
  try {
    const raw = sessionStorage.getItem(messageCacheKey(sessionId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

function hasInFlightMessages(msgs: ChatMessageItem[]): boolean {
  return msgs.some(m => m.id?.startsWith('streaming-'))
}

export function createChatMessageState(
  getCurrentSessionId: () => string | null,
  switchSession?: (id: string) => void,
) {
  const messagesBySession = ref<Record<string, ChatMessageItem[]>>({})
  const activeSkillsBySession = ref<Record<string, Array<{ id: string; name: string }>>>({})
  const messagesLoading = ref(false)
  let realtimeReady = false

  const currentMessages = computed(() => {
    const sessionId = getCurrentSessionId()
    return sessionId ? (messagesBySession.value[sessionId] || []) : []
  })

  const currentActiveSkills = computed(() => {
    const sessionId = getCurrentSessionId()
    return sessionId ? (activeSkillsBySession.value[sessionId] || []) : []
  })

  const getMessages = (sessionId: string) => messagesBySession.value[sessionId] || []

  const setMessages = (sessionId: string, msgs: ChatMessageItem[]) => {
    messagesBySession.value = { ...messagesBySession.value, [sessionId]: msgs }
    persistMessageCache(sessionId, msgs)
  }

  const updateMessages = (sessionId: string, updater: (msgs: ChatMessageItem[]) => void) => {
    const next = [...getMessages(sessionId)]
    updater(next)
    setMessages(sessionId, next)
  }

  const setActiveSkills = (sessionId: string, skills: Array<{ id: string; name: string }>) => {
    activeSkillsBySession.value = { ...activeSkillsBySession.value, [sessionId]: skills }
  }

  const appendMessage = (sessionId: string, message: ChatMessageItem) => {
    updateMessages(sessionId, msgs => { msgs.push(message) })
  }

  const loadSessionMessages = async (sessionId: string) => {
    const wsStore = useWsStore()
    messagesLoading.value = true

    const cached = readMessageCache(sessionId)
    if (cached?.length) {
      setMessages(sessionId, cached)
    }

    try {
      const history = await sessionsApi.getMessages(sessionId)
      const fromApi: ChatMessageItem[] = history.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      }))

      const current = getMessages(sessionId)
      const generating = wsStore.isGenerating && getCurrentSessionId() === sessionId
      const inFlight = hasInFlightMessages(current)

      if ((generating || inFlight) && (current.length > fromApi.length || inFlight)) {
        return
      }

      setMessages(sessionId, fromApi)
    } catch (e) {
      console.error('加载会话历史失败', e)
      if (!getMessages(sessionId).length) {
        setMessages(sessionId, [])
      }
    } finally {
      messagesLoading.value = false
    }
  }

  const initChatRealtime = () => {
    if (realtimeReady) return
    realtimeReady = true

    const wsStore = useWsStore()
    const { t } = useI18n()
    const reminderNotificationsStore = useReminderNotificationsStore()

    wsStore.connect()
    wsStore.subscribe({
      onMessage: async (data: any) => {
        const sessionId = data.session_id as string | undefined

        if (data.type === 'text_chunk') {
          if (!sessionId) return
          const streamId = `streaming-${sessionId}`
          updateMessages(sessionId, msgs => {
            const lastMsg = msgs[msgs.length - 1]
            if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === streamId) {
              lastMsg.content += data.content
            }
          })
        } else if (data.type === 'warning') {
          if (!sessionId) return
          appendMessage(sessionId, {
            id: `${Date.now()}_warn`,
            role: 'system',
            content: `⚠️ ${data.message}`,
            timestamp: data.timestamp,
          })
        } else if (data.type === 'cron_reminder') {
          const currentId = getCurrentSessionId()
          const shouldShowInChat = !(currentId && sessionId && sessionId !== currentId)
          if (shouldShowInChat && sessionId) {
            appendMessage(sessionId, {
              id: `${Date.now()}_cron_reminder`,
              role: 'system',
              content: `⏰ ${data.message}`,
              timestamp: data.timestamp,
            })
          }
          try {
            await reminderNotificationsStore.refreshAfterRealtimeReminder()
          } catch {}
        } else if (data.type === 'thinking_start') {
          if (!sessionId) return
          appendMessage(sessionId, {
            id: `streaming-${sessionId}`,
            role: 'assistant',
            content: '',
            timestamp: data.timestamp,
            thinking: { isActive: true, steps: [] },
          })
        } else if (data.type === 'thinking_step') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const last = msgs[msgs.length - 1]
            if (last && last.role === 'assistant' && last.thinking) {
              last.thinking.steps.push({
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                step: data.step || '',
                title: data.title || '',
                detail: data.detail,
                timestamp: data.timestamp || '',
              })
            }
          })
        } else if (data.type === 'thinking_complete') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            for (let i = msgs.length - 1; i >= 0; i--) {
              if (msgs[i].role === 'assistant' && msgs[i].thinking) {
                msgs[i].thinking!.isActive = false
                break
              }
            }
          })
        } else if (data.type === 'tool_calling') {
          if (!sessionId) return
          const streamId = `streaming-${sessionId}`
          updateMessages(sessionId, msgs => {
            let last = msgs[msgs.length - 1]
            if (!last || last.role !== 'assistant' || last.id !== streamId) {
              msgs.push({
                id: streamId,
                role: 'assistant',
                content: '',
                timestamp: data.timestamp || new Date().toISOString(),
                toolCalls: [],
              })
              last = msgs[msgs.length - 1]
            }
            if (!last.toolCalls) last.toolCalls = []
            const callId = `${data.tool}-${Date.now()}`
            last.toolCalls.push({
              id: callId,
              tool: data.tool,
              parameters: data.parameters || {},
              timestamp: data.timestamp || new Date().toISOString(),
            })
          })
        } else if (data.type === 'tool_result') {
          if (!sessionId) return
          const streamId = `streaming-${sessionId}`
          updateMessages(sessionId, msgs => {
            const last = msgs[msgs.length - 1]
            if (!last || last.role !== 'assistant' || last.id !== streamId) return
            if (!last.toolCalls?.length) {
              last.toolCalls = [{
                id: `${data.tool}-result`,
                tool: data.tool,
                timestamp: data.timestamp || new Date().toISOString(),
              }]
            }
            const tc = [...(last.toolCalls || [])].reverse().find(t => t.tool === data.tool && t.success === undefined)
              || last.toolCalls![last.toolCalls!.length - 1]
            tc.success = data.success
            tc.output = data.output
            tc.error = data.error
            tc.duration = data.duration
            tc.metadata = data.metadata
          })
        } else if (data.type === 'done' || data.type === 'generation_end' || data.type === 'generation_stopped') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const lastMsg = msgs[msgs.length - 1]
            if (lastMsg?.id?.startsWith('streaming-')) {
              lastMsg.id = `msg-${Date.now()}`
            }
            if (lastMsg?.thinking?.isActive) {
              lastMsg.thinking.isActive = false
            }
          })
          if (data.type === 'generation_stopped') {
            appendMessage(sessionId, {
              id: `${Date.now()}_stopped`,
              role: 'system',
              content: `⏹ ${t('chat.generationStopped')}`,
              timestamp: data.timestamp || new Date().toISOString(),
            })
          }
        } else if (data.type === 'run_started') {
          // v5.1.0: store run_id for the current execution
          if (!sessionId) return
          const runData = { run_id: data.run_id, started_at: data.timestamp }
          updateMessages(sessionId, msgs => {
            const lastMsg = msgs[msgs.length - 1]
            if (lastMsg?.id?.startsWith('streaming-')) {
              ;(lastMsg as any)._run = runData
            }
          })
        } else if (data.type === 'run_completed' || data.type === 'run_failed') {
          // v5.1.0: run finished — update the streaming message with run status
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const lastMsg = msgs[msgs.length - 1]
            if (lastMsg?.id?.startsWith('streaming-')) {
              ;(lastMsg as any)._run = {
                ...((lastMsg as any)._run || {}),
                run_id: data.run_id,
                status: data.type === 'run_completed' ? 'completed' : 'failed',
                error: data.error,
              }
            }
          })
        } else if (data.type === 'error') {
          if (!sessionId) return
          appendMessage(sessionId, {
            id: data.session_id,
            role: 'system',
            content: `Error: ${data.message}`,
            timestamp: data.timestamp,
          })
        } else if (data.type === 'task_created' || data.type === 'task_updated') {
          if (!sessionId) return
          const task = data.payload?.task || data.task
          if (!task) return
          updateMessages(sessionId, msgs => {
            const existing = msgs.find(m => m.task?.id === task.id)
            if (existing) {
              existing.task = task
            } else {
              msgs.push({
                id: `task-${task.id}`,
                role: 'task',
                content: '',
                timestamp: data.timestamp,
                task,
              })
            }
          })
        } else if (data.type === 'step_verified' || data.type === 'step_retrying') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const taskMsg = msgs.find(m => m.task?.id === data.task_id)
            if (!taskMsg?.task) return
            const step = taskMsg.task.steps?.find((s: any) => s.id === data.step_id || s.step_order === data.step_id)
            if (step) {
              step.status = data.type === 'step_verified' ? 'completed' : 'running'
              taskMsg.task.current_step = Math.max(taskMsg.task.current_step, step.step_order || 0)
            }
          })
        } else if (data.type === 'task_completed') {
          if (!sessionId) return
          const tid = data.payload?.task_id
          if (!tid) return
          updateMessages(sessionId, msgs => {
            const existing = msgs.find(m => m.task?.id === tid)
            if (existing?.task) {
              existing.task.status = 'completed'
              if (data.payload?.artifacts) existing.task.artifacts = data.payload.artifacts
            }
          })
        } else if (data.type === 'task_aborted') {
          if (!sessionId) return
          const tid = data.payload?.task_id || data.task_id
          if (!tid) return
          updateMessages(sessionId, msgs => {
            const existing = msgs.find(m => m.task?.id === tid)
            if (existing?.task) existing.task.status = 'aborted'
          })
        } else if (data.type === 'plan_created') {
          if (!sessionId) return
          appendMessage(sessionId, {
            id: `plan_${Date.now()}`,
            role: 'plan',
            content: JSON.stringify(data.plan),
            timestamp: data.timestamp,
            plan: data.plan,
            planSteps: data.plan.steps.map((s: any) => ({ ...s, status: 'pending' })),
          })
        } else if (data.type === 'plan_step_start') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const planMsg = [...msgs].reverse().find(m => m.planSteps)
            const step = planMsg?.planSteps?.find((s: any) => s.id === data.step_id)
            if (step) step.status = 'running'
          })
        } else if (data.type === 'plan_step_complete') {
          if (!sessionId) return
          updateMessages(sessionId, msgs => {
            const planMsg = [...msgs].reverse().find(m => m.planSteps)
            const step = planMsg?.planSteps?.find((s: any) => s.id === data.step_id)
            if (step) {
              step.status = data.success ? 'completed' : 'failed'
              step.output = data.output
              step.error = data.error
            }
          })
        } else if (data.type === 'plan_step_failed') {
          const decision = confirm(t('chat.stepFailedConfirm', { stepId: data.step_id, error: data.error }))
          wsStore.send({
            type: 'user_decision',
            session_id: data.session_id,
            step_id: data.step_id,
            decision: decision ? 'retry' : 'abort',
          })
        } else if (data.type === 'command_result') {
          if (!sessionId) return
          appendMessage(sessionId, {
            id: `${Date.now()}_cmd`,
            role: 'system',
            content: data.message,
            timestamp: data.timestamp,
          })
        } else if (data.type === 'session_changed') {
          if (data.new_session_id) {
            switchSession?.(data.new_session_id)
            setMessages(data.new_session_id, [])
            void loadSessionMessages(data.new_session_id)
          }
        } else if (data.type === 'skills_active') {
          if (!sessionId) return
          setActiveSkills(sessionId, Array.isArray(data.skills) ? data.skills : [])
        } else if (data.type === 'confirmation_required') {
          const ok = confirm(t('chat.confirmationRequired', { message: data.message }))
          wsStore.send({
            type: 'user_decision',
            session_id: data.session_id,
            decision: ok ? 'allow' : 'deny',
          })
        }
      },
    })
  }

  return {
    messagesBySession,
    messagesLoading,
    currentMessages,
    currentActiveSkills,
    getMessages,
    setMessages,
    appendMessage,
    loadSessionMessages,
    setActiveSkills,
    initChatRealtime,
  }
}
