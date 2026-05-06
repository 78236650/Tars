// TARS Zustand App Store
// 全局应用状态管理

import { create } from 'zustand'
import type { WebSocketEvent } from '../hooks/useWebSocket'

interface AppState {
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
  sessionId: string
  messages: WebSocketEvent[]
  
  setConnectionStatus: (status: AppState['connectionStatus']) => void
  setSessionId: (id: string) => void
  addMessage: (message: WebSocketEvent) => void
  clearMessages: () => void
}

export const useAppStore = create<AppState>((set) => ({
  connectionStatus: 'disconnected',
  sessionId: '',
  messages: [],
  
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setSessionId: (id) => set({ sessionId: id }),
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  clearMessages: () => set({ messages: [] })
}))
