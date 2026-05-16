import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LongtermMemoryResponse, MemoryItem, MemoryMergeResponse } from '@/types'
import { memoryApi } from '@/api'
import LongtermMemoryTab from './LongtermMemoryTab.vue'
import MergePreviewDialog from './MergePreviewDialog.vue'

vi.mock('@/api', () => ({
  memoryApi: {
    getLongterm: vi.fn(),
    updateMemory: vi.fn(),
    deleteMemory: vi.fn(),
    pinMemory: vi.fn(),
    mergeMemories: vi.fn(),
  },
}))

const baseMemory: MemoryItem = {
  id: 'memory-1',
  content: '原始长期记忆内容',
  summary: '长期记忆摘要',
  category: 'fact',
  importance: 0.8,
  created_at: '2026-05-16T10:00:00Z',
  updated_at: '2026-05-16T10:00:00Z',
  last_accessed: '2026-05-16T10:00:00Z',
  source: 'manual',
  pinned: false,
  compressed_from: [],
  memory_type: 'longterm',
  event_time: '2026-05-16T10:00:00Z',
  entity_refs: ['TARS'],
}

const longtermResponse: LongtermMemoryResponse = {
  page: 1,
  page_size: 20,
  total: 1,
  groups: [
    {
      group_name: 'TARS',
      items: [baseMemory],
    },
  ],
}

const mergePreview: MemoryMergeResponse = {
  preview_only: true,
  merged_content: '压缩后的摘要',
  source_memory_ids: ['memory-1', 'memory-2'],
  importance: 0.8,
  memory_type: 'compressed',
  entity_refs: ['TARS'],
}

describe('memory dialogs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(memoryApi.getLongterm).mockResolvedValue(longtermResponse)
    vi.mocked(memoryApi.updateMemory).mockResolvedValue(baseMemory)
  })

  it('opens merge preview inside the shared dialog shell', () => {
    const wrapper = mount(MergePreviewDialog, {
      props: {
        open: true,
        loading: false,
        preview: mergePreview,
        selectedCount: 2,
      },
    })

    expect(wrapper.text()).toContain('压缩后的摘要')
    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
  })

  it('opens longterm memory editing inside the shared dialog shell', async () => {
    const wrapper = mount(LongtermMemoryTab, {
      global: {
        stubs: {
          MergePreviewDialog: true,
          MemoryCard: {
            props: ['memory'],
            template: `
              <div>
                <span>{{ memory.content }}</span>
                <button data-test="edit-memory" @click="$emit('edit')">编辑</button>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()
    await wrapper.find('[data-test="edit-memory"]').trigger('click')

    expect(wrapper.text()).toContain('编辑长期记忆')
    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(true)
  })
})
