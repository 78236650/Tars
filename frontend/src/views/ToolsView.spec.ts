import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useI18n } from '@/i18n'
import ToolsView from './ToolsView.vue'

const apiMocks = vi.hoisted(() => ({
  listTools: vi.fn(),
  listSkills: vi.fn(),
  getStats: vi.fn(),
  getCatalog: vi.fn(),
  searchCatalog: vi.fn(),
  install: vi.fn(),
  createPromptSkill: vi.fn(),
  deleteSkill: vi.fn(),
  enableSkill: vi.fn(),
  disableSkill: vi.fn(),
  archive: vi.fn(),
  activate: vi.fn(),
}))

vi.mock('@/api', () => ({
  toolsApi: {
    listTools: apiMocks.listTools,
  },
  skillsApi: {
    listSkills: apiMocks.listSkills,
    getStats: apiMocks.getStats,
    createPromptSkill: apiMocks.createPromptSkill,
    deleteSkill: apiMocks.deleteSkill,
    enableSkill: apiMocks.enableSkill,
    disableSkill: apiMocks.disableSkill,
    archive: apiMocks.archive,
    activate: apiMocks.activate,
  },
  skillhubApi: {
    getCatalog: apiMocks.getCatalog,
    search: apiMocks.searchCatalog,
    install: apiMocks.install,
  },
}))

const flushPromises = async () => {
  await Promise.resolve()
  await nextTick()
}

describe('ToolsView', () => {
  beforeEach(() => {
    localStorage.clear()
    useI18n().setLocale('zh')

    apiMocks.listTools.mockResolvedValue({
      data: {
        tools: [
          {
            id: 'file',
            name: 'file',
            icon: '🔧',
            type: 'builtin',
            source: 'builtin',
            status: 'active',
            description: '读取本地文件内容，支持指定行范围。',
          },
          {
            id: 'calculator',
            name: 'calculator',
            icon: '🧮',
            type: 'builtin',
            source: 'builtin',
            status: 'active',
            description: '计算数学表达式。支持四则运算（+-*/），幂运算（**），以及 sqrt/log/sin/cos/exp/pi/e 等数学函数。',
          },
        ],
      },
    })
    apiMocks.listSkills.mockResolvedValue({ data: { skills: [] } })
    apiMocks.getStats.mockResolvedValue({ data: { items: [] } })
    apiMocks.getCatalog.mockResolvedValue({ data: { results: [] } })
    apiMocks.searchCatalog.mockResolvedValue({ data: { results: [] } })
    apiMocks.install.mockResolvedValue({ data: {} })
  })

  it('uses localized builtin descriptions for english list, search, and detail views', async () => {
    useI18n().setLocale('en')

    const wrapper = mount(ToolsView, {
      global: {
        stubs: {
          ToolCard: {
            props: ['tool'],
            template: '<button class="tool-card" @click="$emit(\'click\', tool)">{{ tool.name }}|{{ tool.description }}</button>',
          },
          ToolDetailModal: {
            props: ['tool'],
            template: '<div class="tool-detail">{{ tool.description }}</div>',
          },
          AddToolModal: true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(apiMocks.listTools).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Read local file contents, including optional line-range reads.')
    expect(wrapper.text()).toContain('Evaluate math expressions with arithmetic, powers, and common functions such as sqrt, log, sin, cos, exp, pi, and e.')
    expect(wrapper.text()).not.toContain('读取本地文件内容，支持指定行范围。')
    expect(wrapper.text()).not.toContain('计算数学表达式。支持四则运算（+-*/），幂运算（**），以及 sqrt/log/sin/cos/exp/pi/e 等数学函数。')

    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('math expressions')
    await nextTick()

    expect(wrapper.findAll('.tool-card')).toHaveLength(1)

    await wrapper.find('.tool-card').trigger('click')
    await nextTick()

    expect(wrapper.find('.tool-detail').text()).toBe('Evaluate math expressions with arithmetic, powers, and common functions such as sqrt, log, sin, cos, exp, pi, and e.')
  })
})
