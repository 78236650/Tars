<template>
  <div class="transcription-list">
    <h3 class="list-title">转录历史</h3>
    <div v-if="transcriptions.length === 0" class="empty-state">
      <p>暂无转录记录</p>
      <p class="hint">上传音频文件开始转录</p>
    </div>
    <div v-else class="list-items">
      <div
        v-for="item in transcriptions"
        :key="item.id"
        class="list-item"
        :class="{ active: selectedId === item.id }"
        @click="selectItem(item)"
      >
        <div class="item-header">
          <span class="file-name">{{ item.file_name || '未知文件' }}</span>
          <span class="status-badge" :class="item.status">
            {{ statusText(item.status) }}
          </span>
        </div>
        <div class="item-meta">
          <span class="meta-item">{{ formatSize(item.file_size) }}</span>
          <span class="meta-item">{{ formatDuration(item.duration) }}</span>
          <span class="meta-item">{{ formatDate(item.created_at) }}</span>
        </div>
        <button
          class="delete-btn"
          @click.stop="deleteItem(item.id)"
          title="删除"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Transcription } from '@/types'

interface Props {
  transcriptions: Transcription[]
  selectedId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [item: Transcription]
  delete: [id: string]
}>()

function selectItem(item: Transcription) {
  emit('select', item)
}

function deleteItem(id: string) {
  if (!confirm('确定要删除这条转录记录吗？')) return
  emit('delete', id)
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}分${s}秒`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.transcription-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.empty-state {
  text-align: center;
  padding: 32px 16px;
  color: #9ca3af;
}

.empty-state .hint {
  font-size: 12px;
  margin-top: 4px;
}

.list-items {
  overflow-y: auto;
  flex: 1;
}

.list-item {
  position: relative;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.list-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.list-item.active {
  border-color: #3b82f6;
  background: #eff6ff;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  padding-right: 24px;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  word-break: break-all;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
  flex-shrink: 0;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.processing {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.completed {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.item-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.meta-item {
  font-size: 11px;
  color: #6b7280;
}

.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px;
  border-radius: 4px;
  color: #9ca3af;
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}

.list-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #dc2626;
  background: #fee2e2;
}
</style>
