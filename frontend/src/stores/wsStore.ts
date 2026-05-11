import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface WsEventHandler {
  onMessage?: (data: any) => void
}

// v2.6: 处理步骤显示
export interface ThinkingStep {
  id: string
  step: string
  title: string
  detail?: string
  timestamp: string
}

export interface ThinkingState {
  isActive: boolean
  steps: ThinkingStep[]
}

export const useWsStore = defineStore('ws', () => {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isGenerating = ref(false)
  const reconnectTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const handlers = ref<WsEventHandler[]>([])

  // v2.6: thinking 状态，按 session_id 索引
  const thinkingStates = ref<Record<string, ThinkingState>>({})

  const connect = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) return

    ws.value = new WebSocket(`ws://localhost:8000/ws`)

    ws.value.onopen = () => {
      isConnected.value = true
      if (reconnectTimer.value) {
        clearTimeout(reconnectTimer.value)
        reconnectTimer.value = null
      }
    }

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'text_chunk' || data.type === 'generation_start' || data.type === 'tool_calling' || data.type === 'tool_result' || data.type === 'thinking_start' || data.type === 'thinking_step') {
        isGenerating.value = true
      } else if (data.type === 'done' || data.type === 'generation_end' || data.type === 'error' || data.type === 'plan_complete') {
        isGenerating.value = false
      }

      // v2.6: 处理 thinking 事件
      if (data.type === 'thinking_start') {
        handleThinkingStart(data.session_id)
      } else if (data.type === 'thinking_step') {
        handleThinkingStep(data.session_id, data)
      } else if (data.type === 'thinking_complete') {
        handleThinkingComplete(data.session_id)
      }

      for (const h of handlers.value) {
        h.onMessage?.(data)
      }
    }

    ws.value.onclose = () => {
      isConnected.value = false
      isGenerating.value = false
      ws.value = null
      // 自动重连
      reconnectTimer.value = setTimeout(connect, 3000)
    }

    ws.value.onerror = () => {
      isConnected.value = false
    }
  }

  const subscribe = (handler: WsEventHandler) => {
    handlers.value.push(handler)
    // 返回取消订阅函数
    return () => {
      const idx = handlers.value.indexOf(handler)
      if (idx >= 0) handlers.value.splice(idx, 1)
    }
  }

  // v2.6: thinking 状态管理方法
  const handleThinkingStart = (sessionId: string) => {
    if (!sessionId) return
    thinkingStates.value[sessionId] = {
      isActive: true,
      steps: []
    }
  }

  const handleThinkingStep = (sessionId: string, data: any) => {
    if (!sessionId) return
    if (!thinkingStates.value[sessionId]) {
      thinkingStates.value[sessionId] = { isActive: true, steps: [] }
    }
    thinkingStates.value[sessionId].steps.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      step: data.step || '',
      title: data.title || '',
      detail: data.detail,
      timestamp: data.timestamp || ''
    })
  }

  const handleThinkingComplete = (sessionId: string) => {
    if (!sessionId) return
    if (thinkingStates.value[sessionId]) {
      thinkingStates.value[sessionId].isActive = false
    }
  }

  const getThinkingState = (sessionId: string): ThinkingState | null => {
    return thinkingStates.value[sessionId] || null
  }

  const clearThinkingState = (sessionId: string) => {
    delete thinkingStates.value[sessionId]
  }

  const send = (payload: any) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(payload))
    }
  }

  return {
    ws,
    isConnected,
    isGenerating,
    thinkingStates,
    handleThinkingStart,
    handleThinkingStep,
    handleThinkingComplete,
    getThinkingState,
    clearThinkingState,
    connect,
    subscribe,
    send,
  }
})
