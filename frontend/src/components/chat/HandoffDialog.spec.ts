import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import HandoffDialog from './HandoffDialog.vue'
import { useChatStore } from '@/stores/chat'
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

vi.mock('@/api', () => ({
  handoffsApi: {
    accept: vi.fn(async () => ({ success: true, handoff_id: 'h1', status: 'accepted' })),
    reject: vi.fn(async () => ({ success: true, handoff_id: 'h1', status: 'rejected' })),
  },
}))

describe('HandoffDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useI18n().setLocale('zh')
    wsHandlers.length = 0
    const chatStore = useChatStore()
    chatStore.currentSessionId = 'sess-1'
  })

  it('opens on subagent_handoff pending_review and calls accept API', async () => {
    const wrapper = mount(HandoffDialog)
    await nextTick()

    wsHandlers[0].onMessage?.({
      type: 'subagent_handoff',
      handoff_id: 'h1',
      parent_session_id: 'sess-1',
      status: 'pending_review',
      subagent_type: 'code',
      task_summary: 'Review PR',
      result_preview: 'Looks good',
    })
    await nextTick()

    expect(wrapper.text()).toContain('code')
    expect(wrapper.text()).toContain('Review PR')

    const acceptBtn = wrapper.findAll('button').find((btn) =>
      btn.text().includes('采纳结果'),
    )
    expect(acceptBtn).toBeTruthy()
    await acceptBtn!.trigger('click')
    await nextTick()

    const { handoffsApi } = await import('@/api')
    expect(handoffsApi.accept).toHaveBeenCalledWith('h1')
  })

  it('ignores subagent_handoff for other sessions and bumps badge count', async () => {
    const chatStore = useChatStore()
    mount(HandoffDialog)
    await nextTick()

    wsHandlers[0].onMessage?.({
      type: 'subagent_handoff',
      handoff_id: 'h2',
      parent_session_id: 'other-session',
      status: 'pending_review',
      subagent_type: 'code',
      task_summary: 'Hidden',
      result_preview: 'Hidden',
    })
    await nextTick()

    expect(chatStore.externalHandoffCount).toBe(1)
  })
})
