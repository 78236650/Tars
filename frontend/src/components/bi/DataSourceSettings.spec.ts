import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { biApi } from '@/api'
import DataSourceSettings from './DataSourceSettings.vue'

const toastSuccess = vi.fn()
const toastError = vi.fn()

vi.mock('@/api', () => ({
  biApi: {
    listDataSources: vi.fn(),
    createDataSource: vi.fn(),
    updateDataSource: vi.fn(),
    deleteDataSource: vi.fn(),
    testConnection: vi.fn(),
    testConnectionConfig: vi.fn(),
    refreshSchema: vi.fn(),
  },
  insightApi: {
    listProfileRuns: vi.fn().mockResolvedValue({ runs: [] }),
  },
}))

vi.mock('@/composables/useBiDataSources', () => ({
  useBiDataSources: () => ({
    datasources: ref([
      {
        id: 'ds-1',
        name: 'Demo DB',
        db_type: 'sqlite',
        readonly: true,
        schema_snapshot: { tables: {} },
        schema_annotations: {},
        connection: { db_type: 'sqlite', database: '/tmp/demo.db' },
        created_at: '',
        updated_at: '',
      },
    ]),
    loadError: ref(''),
    loading: ref(false),
    loadDataSources: vi.fn().mockResolvedValue([]),
  }),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: toastSuccess,
    error: toastError,
    info: vi.fn(),
    toasts: ref([]),
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

describe('DataSourceSettings actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows toast feedback after test connection', async () => {
    vi.mocked(biApi.testConnection).mockResolvedValue({ success: true, message: '连接成功' })

    const wrapper = mount(DataSourceSettings, {
      global: {
        stubs: {
          SchemaAnnotator: { template: '<div />' },
          ConnectionFields: { template: '<div class="connection-fields-stub" />' },
          AppSurfaceDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          AppSurfaceDrawer: { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()
    await wrapper.find('.btn-icon').trigger('click')
    await flushPromises()

    expect(biApi.testConnection).toHaveBeenCalledWith('ds-1')
    expect(toastSuccess).toHaveBeenCalled()
  })
})
