import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { knowledgeApi } from '@/api'
import DocumentUploader from './DocumentUploader.vue'

vi.mock('@/api', () => ({
  knowledgeApi: {
    uploadDocument: vi.fn(),
  },
}))

describe('DocumentUploader doc_type', () => {
  it('passes selected doc_type to upload API', async () => {
    vi.mocked(knowledgeApi.uploadDocument).mockResolvedValue({
      success: true,
      document: { id: 'd1', status: 'pending', doc_type: 'metrics' },
    })

    const wrapper = mount(DocumentUploader, {
      props: { collectionId: 'c1', defaultDocType: 'policy' },
    })

    await wrapper.find('.doc-type-select').setValue('metrics')

    const file = new File(['hello'], 'data.csv', { type: 'text/csv' })
    const input = wrapper.find('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    await wrapper.find('input[type="file"]').trigger('change')
    await flushPromises()

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledWith('c1', file, 'metrics')
  })

  it('pre-selects collection default doc_type when provided', async () => {
    vi.mocked(knowledgeApi.uploadDocument).mockResolvedValue({
      success: true,
      document: { id: 'd2', status: 'pending', doc_type: 'policy' },
    })

    const wrapper = mount(DocumentUploader, {
      props: { collectionId: 'c1', defaultDocType: 'policy' },
    })

    expect((wrapper.find('.doc-type-select').element as HTMLSelectElement).value).toBe('policy')

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    const input = wrapper.find('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    await wrapper.find('input[type="file"]').trigger('change')
    await flushPromises()

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledWith('c1', file, 'policy')
  })

  it('passes undefined when auto infer is selected', async () => {
    vi.mocked(knowledgeApi.uploadDocument).mockResolvedValue({
      success: true,
      document: { id: 'd3', status: 'pending', doc_type: 'generic' },
    })

    const wrapper = mount(DocumentUploader, {
      props: { collectionId: 'c1' },
    })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    const input = wrapper.find('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    await wrapper.find('input[type="file"]').trigger('change')
    await flushPromises()

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledWith('c1', file, undefined)
  })
})
