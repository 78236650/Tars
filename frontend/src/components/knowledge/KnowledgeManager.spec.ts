import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { knowledgeApi } from '@/api'
import KnowledgeManager from './KnowledgeManager.vue'

vi.mock('@/api', () => ({
  knowledgeApi: {
    listCollections: vi.fn(),
    listDocuments: vi.fn(),
    createCollection: vi.fn(),
    deleteCollection: vi.fn(),
    deleteDocument: vi.fn(),
    queryCollection: vi.fn(),
  },
}))

describe('KnowledgeManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(knowledgeApi.listCollections).mockResolvedValue({
      collections: [],
    })
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue({
      documents: [],
    })
  })

  it('uses the shared dialog surface for the create collection flow', async () => {
    const wrapper = mount(KnowledgeManager, {
      global: {
        stubs: {
          DocumentUploader: {
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
