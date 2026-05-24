import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import QueueStatus from './QueueStatus.vue'
import { useI18n } from '@/i18n'

const wsHandlers: Array<{ onMessage?: (data: any) => void }> = []

vi.mock('@/stores/wsStore', () => ({
  useWsStore: () => ({
    subscribe: (handler: { onMessage?: (data: any) => void }) => {
      wsHandlers.push(handler)
      return () => {
        const idx = wsHandlers.indexOf(handler)
        if (idx >= 0) wsHandlers.splice(idx, 1)
      }
    },
  }),
}))

describe('QueueStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    useI18n().setLocale('zh')
    wsHandlers.length = 0
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function emitWs(data: Record<string, unknown>) {
    wsHandlers[0]?.onMessage?.(data)
  }

  it('shows follow-up queued banner on queue_status with pending count', async () => {
    const wrapper = mount(QueueStatus)
    await nextTick()
    expect(wsHandlers.length).toBe(1)

    emitWs({ type: 'queue_status', session_id: 'sess-1', pending: 2 })
    await nextTick()

    expect(wrapper.text()).toContain('消息已排队')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
  })

  it('hides banner when queue_status pending drops to zero', async () => {
    const wrapper = mount(QueueStatus)
    await nextTick()

    emitWs({ type: 'queue_status', session_id: 'sess-1', pending: 1 })
    await nextTick()
    expect(wrapper.text()).toContain('消息已排队')

    emitWs({ type: 'queue_status', session_id: 'sess-1', pending: 0 })
    await nextTick()
    expect(wrapper.text()).toBe('')
  })

  it('shows rate_limited error message from WS', async () => {
    const wrapper = mount(QueueStatus)
    await nextTick()

    emitWs({
      type: 'error',
      code: 'rate_limited',
      message: '请求过于频繁，请稍后再试',
    })
    await nextTick()

    expect(wrapper.text()).toContain('请求过于频繁，请稍后再试')
  })

  it('renders follow-up queued copy in English locale', async () => {
    useI18n().setLocale('en')
    const wrapper = mount(QueueStatus)
    await nextTick()

    emitWs({ type: 'queue_status', session_id: 'sess-1', pending: 3 })
    await nextTick()

    expect(wrapper.text()).toContain('Message queued until the current reply finishes')
    expect(wrapper.text()).toContain('3')
  })

  it('auto-hides queued banner after five seconds', async () => {
    const wrapper = mount(QueueStatus)
    await nextTick()

    emitWs({ type: 'queue_status', session_id: 'sess-1', pending: 1 })
    await nextTick()
    expect(wrapper.text()).toContain('消息已排队')

    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(wrapper.text()).toBe('')
  })
})
