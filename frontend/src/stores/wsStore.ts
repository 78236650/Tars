import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface WsEventHandler {
  onMessage?: (data: any) => void
}

export const useWsStore = defineStore('ws', () => {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isGenerating = ref(false)
  const reconnectTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const handlers = ref<WsEventHandler[]>([])

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

      if (data.type === 'text_chunk' || data.type === 'generation_start' || data.type === 'tool_calling' || data.type === 'tool_result') {
        isGenerating.value = true
      } else if (data.type === 'done' || data.type === 'generation_end' || data.type === 'error' || data.type === 'plan_complete') {
        isGenerating.value = false
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

  const send = (payload: any) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(payload))
    }
  }

  return {
    ws,
    isConnected,
    isGenerating,
    connect,
    subscribe,
    send,
  }
})
