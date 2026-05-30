<template>
  <div class="transcription-list">
    <h3 class="list-title">{{ t('meeting.historyTitle') }}</h3>
    <div v-if="transcriptions.length === 0" class="empty-state">
      <p>{{ t('meeting.emptyTitle') }}</p>
      <p class="hint">{{ t('meeting.emptyHint') }}</p>
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
          <span class="file-name">{{ item.file_name || t('meeting.unknownFile') }}</span>
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
          :title="t('common.delete')"
        >
          <BaseIcon icon="lucide:trash-2" :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Transcription } from '@/types'
import { useI18n } from '@/i18n'
import BaseIcon from '@/components/common/BaseIcon.vue'

interface Props {
  transcriptions: Transcription[]
  selectedId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [item: Transcription]
  delete: [id: string]
}>()
const { t, locale } = useI18n()

function selectItem(item: Transcription) {
  emit('select', item)
}

function deleteItem(id: string) {
  if (!confirm(t('meeting.deleteConfirm'))) return
  emit('delete', id)
}

function statusText(status: string): string {
  return t(`meeting.status.${status}`)
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
  return locale.value === 'zh' ? `${m}分${s}秒` : `${m}m ${s}s`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
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
  color: #d6d3d1;
}

.empty-state {
  text-align: center;
  padding: 32px 16px;
  color: #78716c;
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
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(245, 158, 11, 0.1);
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.list-item:hover {
  border-color: rgba(245, 158, 11, 0.3);
}

.list-item.active {
  border-color: #d97706;
  background: rgba(217, 119, 6, 0.08);
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
  color: #e7e5e4;
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
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.status-badge.processing {
  background: rgba(217, 119, 6, 0.12);
  color: #f59e0b;
}

.status-badge.completed {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
}

.status-badge.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}

.item-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.meta-item {
  font-size: 11px;
  color: #78716c;
}

.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px;
  border-radius: 4px;
  color: #78716c;
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
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
}
</style>
