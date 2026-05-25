import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { biApi } from '@/api'
import BiAnalyticsView from '@/views/BiAnalyticsView.vue'

const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {},
  }),
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}))

vi.mock('@/api', () => ({
  biApi: {
    listDataSources: vi.fn(),
    executeQuery: vi.fn(),
    generateChart: vi.fn(),
  },
  insightApi: {
    listProfileRuns: vi.fn().mockResolvedValue({ runs: [] }),
  },
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    toasts: ref([]),
  }),
}))

describe('BiAnalyticsView query tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(biApi.listDataSources).mockResolvedValue({
      datasources: [
        {
          id: 'ds-new',
          name: 'New DB',
          db_type: 'mysql',
          readonly: true,
          schema_snapshot: { tables: {} },
          schema_annotations: {},
          created_at: '',
          updated_at: '',
        },
      ],
    })
  })

  it('reloads datasources when switching to query tab', async () => {
    const wrapper = mount(BiAnalyticsView, {
      global: {
        stubs: {
          DataSourceSettings: { template: '<div />' },
          ChartRenderer: { template: '<div />' },
        },
      },
    })

    await flushPromises()
    expect(biApi.listDataSources).not.toHaveBeenCalled()

    await wrapper.findAll('.tab-btn')[1].trigger('click')
    await flushPromises()

    expect(biApi.listDataSources).toHaveBeenCalledTimes(1)
    const select = wrapper.find('.ds-select')
    expect(select.findAll('option')).toHaveLength(2)
    expect((select.element as HTMLSelectElement).value).toBe('ds-new')
  })
})
