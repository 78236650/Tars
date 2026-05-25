import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import ChatView from './ChatView.vue'
import { useI18n } from '@/i18n'

const stopGeneration = vi.fn()

vi.mock('@/stores/wsStore', () => ({
  useWsStore: () => ({
    isConnected: true,
    isGenerating: true,
    connect: vi.fn(),
    subscribe: vi.fn(() => () => {}),
    send: vi.fn(),
    stopGeneration,
  }),
}))

vi.mock('@/stores/chat', () => ({
  useChatStore: () => ({
    currentSessionId: 'sess-1',
    currentMessages: [],
    currentActiveSkills: [],
    messagesLoading: false,
    externalApprovalCount: 0,
    externalHandoffCount: 0,
    initChatRealtime: vi.fn(),
    initIfEmpty: vi.fn(),
    loadSessionMessages: vi.fn(),
    appendUserMessage: vi.fn(),
    appendMessage: vi.fn(),
    clearActiveSkills: vi.fn(),
    createSession: vi.fn(),
    switchSession: vi.fn(),
  }),
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    currentModel: 'test-model',
    loadModels: vi.fn(),
  }),
}))

vi.mock('@/stores/reminderNotifications', () => ({
  useReminderNotificationsStore: () => ({
    loadList: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: false }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api', () => ({
  biApi: { listDataSources: vi.fn().mockResolvedValue({ datasources: [] }) },
  insightApi: {
    version: vi.fn().mockResolvedValue({ phase: {} }),
    ask: vi.fn(),
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

describe('ChatView stop button', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useI18n().setLocale('zh')
    stopGeneration.mockClear()
  })

  it('shows stop button while generating and calls stopGeneration', async () => {
    const wrapper = mount(ChatView, {
      global: {
        stubs: {
          ChatPanel: true,
          ActiveSkillsBar: true,
          WorkflowStrip: true,
          KnowledgeCitationPanel: true,
          QueueStatus: true,
          WarningBanner: true,
          ApprovalDialog: true,
          HandoffDialog: true,
        },
      },
    })

    await nextTick()

    const stopBtn = wrapper.find('[data-test="chat-stop-button"]')
    expect(stopBtn.exists()).toBe(true)
    expect(stopBtn.text()).toContain('停止')

    await stopBtn.trigger('click')
    expect(stopGeneration).toHaveBeenCalledWith('sess-1')
  })
})
