import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { biApi } from '@/api'
import DataSourceSettings from './DataSourceSettings.vue'

vi.mock('@/api', () => ({
  biApi: {
    listDataSources: vi.fn(),
    createDataSource: vi.fn(),
    deleteDataSource: vi.fn(),
    testConnection: vi.fn(),
    refreshSchema: vi.fn(),
  },
}))

describe('DataSourceSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(biApi.listDataSources).mockResolvedValue({
      datasources: [],
    })
  })

  it('uses the shared dialog surface for the create data source flow', async () => {
    const wrapper = mount(DataSourceSettings, {
      global: {
        stubs: {
          SchemaAnnotator: {
            template: '<div />',
          },
        },
      },
    })

    await flushPromises()
    await wrapper.find('.btn-primary').trigger('click')

    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
  })
})
