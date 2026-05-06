// TARS WebSocket Hook
// 管理 WebSocket 连接、心跳、重连

import { useEffect, useRef, useState, useCallback } from 'react'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

export interface WebSocketEvent {
  type: string
  session_id?: string
  [key: string]: any
}

interface UseWebSocketOptions {
  url: string
  reconnectInterval?: number
  pingInterval?: number
  onEvent?: (event: WebSocketEvent) => void
  onConnected?: (sessionId: string) => void
}

export function useWebSocket({
  url,
  reconnectInterval = 3000,
  pingInterval = 30000,
  onEvent,
  onConnected
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [sessionId, setSessionId] = useState<string>('')
  const wsRef = useRef<WebSocket | null>(null)
  const pingTimerRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    console.log('[WebSocket] Connecting...')
    setStatus('connecting')

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setStatus('connected')

        // 启动心跳
        if (pingTimerRef.current) clearInterval(pingTimerRef.current)
        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
          }
        }, pingInterval)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[WebSocket] Received:', data)

          // 处理 welcome 事件
          if (data.type === 'welcome' && data.session_id) {
            setSessionId(data.session_id)
            onConnected?.(data.session_id)
          }

          // 回调事件
          onEvent?.(data)
        } catch (e) {
          console.error('[WebSocket] Parse error:', e)
        }
      }

      ws.onclose = () => {
        console.log('[WebSocket] Closed')
        setStatus('reconnecting')
        if (pingTimerRef.current) clearInterval(pingTimerRef.current)

        // 自动重连
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = setTimeout(() => {
          connect()
        }, reconnectInterval)
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
      }
    } catch (e) {
      console.error('[WebSocket] Connection failed:', e)
      setStatus('reconnecting')
    }
  }, [url, reconnectInterval, pingInterval, onConnected, onEvent])

  const disconnect = useCallback(() => {
    console.log('[WebSocket] Disconnecting...')
    if (pingTimerRef.current) clearInterval(pingTimerRef.current)
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('disconnected')
  }, [])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('[WebSocket] Not connected, cannot send message')
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    status,
    sessionId,
    sendMessage
  }
}
