import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { knowledgeApi } from '@/api'
import KnowledgeManager from './KnowledgeManager.vue'
import DocumentDetailDrawer from './DocumentDetailDrawer.vue'

vi.mock('@/api', () => ({
  knowledgeApi: {
    listCollections: vi.fn(),
    listDocuments: vi.fn(),
    createCollection: vi.fn(),
    deleteCollection: vi.fn(),
    deleteDocument: vi.fn(),
    queryCollection: vi.fn(),
    getDocumentProfile: vi.fn(),
    getDocumentStatus: vi.fn(),
    getDocumentPassages: vi.fn(),
    reEnrichDocument: vi.fn(),
  },
}))

const mockProfile = {
  doc_id: 'doc-1',
  file_name: '制度.txt',
  doc_type: 'policy',
  status: 'ready',
  title: '测试制度',
  one_liner: '规范流程',
  summary: '这是摘要',
  key_points: ['要点1', '要点2'],
  confidence: 0.9,
  profile_ready: true,
}

describe('KnowledgeManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(knowledgeApi.listCollections).mockResolvedValue({
      collections: [{ id: 'c1', name: 'Test', created_at: '', updated_at: '' }],
    })
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue({
      documents: [
        {
          id: 'doc-1',
          file_name: '制度.txt',
          file_type: '.txt',
          chunk_count: 3,
          status: 'ready',
          created_at: '',
          doc_type: 'policy',
          profile_ready: true,
          one_liner: '规范流程',
        },
      ],
    })
    vi.mocked(knowledgeApi.getDocumentProfile).mockResolvedValue(mockProfile)
  })

  it('uses the shared dialog surface for the create collection flow', async () => {
    const wrapper = mount(KnowledgeManager, {
      global: {
        stubs: {
          DocumentUploader: { template: '<div />' },
          DocumentDetailDrawer: { template: '<div data-test="detail-drawer-stub" />' },
        },
      },
    })

    await flushPromises()
    await wrapper.find('.btn-primary').trigger('click')

    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
  })

  it('opens document detail drawer when clicking a document row', async () => {
    const wrapper = mount(KnowledgeManager, {
      global: {
        stubs: {
          DocumentUploader: { template: '<div />' },
        },
      },
    })

    await flushPromises()
    await wrapper.find('[data-test="doc-row"]').trigger('click')
    await flushPromises()

    const drawer = wrapper.findComponent(DocumentDetailDrawer)
    expect(drawer.exists()).toBe(true)
    expect(drawer.props('open')).toBe(true)
    expect(knowledgeApi.getDocumentProfile).toHaveBeenCalledWith('c1', 'doc-1')
  })
})

describe('DocumentDetailDrawer', () => {
  it('renders summary and key_points from profile API', async () => {
    vi.mocked(knowledgeApi.getDocumentProfile).mockResolvedValue(mockProfile)

    const wrapper = mount(DocumentDetailDrawer, {
      props: {
        open: true,
        collectionId: 'c1',
        document: {
          id: 'doc-1',
          file_name: '制度.txt',
          file_type: '.txt',
          chunk_count: 3,
          status: 'ready',
          created_at: '',
        },
      },
      global: {
        stubs: { teleport: true },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-test="key-points"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('要点1')
    expect(wrapper.text()).toContain('这是摘要')
  })

  it('shows re-enrich when profile has no summary', async () => {
    vi.mocked(knowledgeApi.getDocumentProfile).mockResolvedValue({
      doc_id: 'doc-1',
      status: 'ready',
      profile_ready: false,
    })

    const wrapper = mount(DocumentDetailDrawer, {
      props: {
        open: true,
        collectionId: 'c1',
        document: {
          id: 'doc-1',
          file_name: 'x.txt',
          file_type: '.txt',
          chunk_count: 1,
          status: 'ready',
          created_at: '',
        },
      },
      global: {
        stubs: { teleport: true },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-test="re-enrich-btn"]').exists()).toBe(true)
  })
})
