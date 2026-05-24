import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import ApprovalDialog from './ApprovalDialog.vue'
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
  approvalsApi: {
    approve: vi.fn(async () => ({ success: true, approval_id: 'a1', status: 'approved' })),
    deny: vi.fn(async () => ({ success: true, approval_id: 'a1', status: 'denied' })),
  },
}))

describe('ApprovalDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useI18n().setLocale('zh')
    wsHandlers.length = 0
    const chatStore = useChatStore()
    chatStore.currentSessionId = 'sess-1'
  })

  it('opens on approval_required WS event and calls approve API', async () => {
    const wrapper = mount(ApprovalDialog)
    await nextTick()
    expect(wsHandlers.length).toBe(1)

    wsHandlers[0].onMessage?.({
      type: 'approval_required',
      approval_id: 'a1',
      session_id: 'sess-1',
      tool_name: 'command',
      arguments_summary: '{"command":"ls"}',
    })
    await nextTick()

    expect(wrapper.text()).toContain('command')
    expect(wrapper.text()).toContain('ls')
    expect(wrapper.text()).toContain('允许执行')

    const approveBtn = wrapper.findAll('button').find((btn) =>
      btn.text().includes('允许执行'),
    )
    expect(approveBtn).toBeTruthy()
    await approveBtn!.trigger('click')
    await nextTick()

    const { approvalsApi } = await import('@/api')
    expect(approvalsApi.approve).toHaveBeenCalledWith('a1')
  })

  it('ignores approval_required for other sessions and bumps badge count', async () => {
    const chatStore = useChatStore()
    const wrapper = mount(ApprovalDialog)
    await nextTick()
    wsHandlers[0].onMessage?.({
      type: 'approval_required',
      approval_id: 'a2',
      session_id: 'other-session',
      tool_name: 'shell',
      arguments_summary: '{}',
    })
    await nextTick()
    expect(wrapper.text()).not.toContain('shell')
    expect(chatStore.externalApprovalCount).toBe(1)
  })
})
