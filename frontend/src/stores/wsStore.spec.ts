import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useWsStore } from './wsStore'

class MockWebSocket {
  static OPEN = 1
  readyState = 1
  onmessage: ((event: MessageEvent) => void) | null = null
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  send = vi.fn()
  constructor(_url: string) {
    queueMicrotask(() => this.onopen?.())
  }
}

describe('wsStore stop generation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('stopGeneration sends stop_generation control message', () => {
    const store = useWsStore()
    store.connect()

    store.stopGeneration('sess-abc')

    expect(store.ws?.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'stop_generation',
        session_id: 'sess-abc',
      }),
    )
  })

  it('clears isGenerating on generation_stopped event', () => {
    const store = useWsStore()
    store.connect()
    store.isGenerating = true

    store.ws!.onmessage?.({
      data: JSON.stringify({
        type: 'generation_stopped',
        session_id: 'sess-abc',
      }),
    } as MessageEvent)

    expect(store.isGenerating).toBe(false)
  })

  it('ignores stopGeneration when session id is empty', () => {
    const store = useWsStore()
    store.connect()

    store.stopGeneration('')

    expect(store.ws?.send).not.toHaveBeenCalled()
  })
})
