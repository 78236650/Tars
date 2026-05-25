<template>
  <div class="document-uploader">
    <div class="uploader-options" @click.stop>
      <label class="doc-type-label">{{ t('knowledge.uploadDocType') }}</label>
      <select v-model="selectedDocType" class="doc-type-select">
        <option value="">{{ t('knowledge.uploadDocTypeAuto') }}</option>
        <option value="policy">{{ t('knowledge.docType.policy') }}</option>
        <option value="proposal">{{ t('knowledge.docType.proposal') }}</option>
        <option value="metrics">{{ t('knowledge.docType.metrics') }}</option>
        <option value="generic">{{ t('knowledge.docType.generic') }}</option>
      </select>
    </div>
    <div
      class="drop-zone"
      :class="{ dragging: isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".txt,.md,.pdf,.docx,.xlsx,.csv,.pptx"
        style="display: none"
        @change="handleFileSelect"
      />
      <div class="drop-text">
        <span class="icon">📁</span>
        <p>{{ t('knowledge.uploadPrompt') }}</p>
        <p class="hint">{{ t('knowledge.uploadHint') }}</p>
      </div>
    </div>

    <div v-if="uploading.length > 0" class="upload-progress">
      <div v-for="item in uploading" :key="item.id" class="progress-item">
        <span class="file-name">{{ item.name }}</span>
        <span class="status">{{ statusText(item) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { knowledgeApi } from '@/api'
import { useI18n } from '@/i18n'

interface Props {
  collectionId: string
  defaultDocType?: string | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  uploaded: [collectionId: string]
}>()

const fileInput = ref<HTMLInputElement>()
const isDragging = ref(false)
const selectedDocType = ref(props.defaultDocType || '')
const uploading = ref<{ id: string; name: string; status: 'uploading' | 'completed' | 'failed'; error?: string }[]>([])
const { t } = useI18n()

watch(
  () => props.defaultDocType,
  (value) => {
    if (!selectedDocType.value) {
      selectedDocType.value = value || ''
    }
  },
)

function triggerFileInput() {
  fileInput.value?.click()
}

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files) {
    uploadFiles(Array.from(files))
  }
}

function handleFileSelect(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files) {
    uploadFiles(Array.from(files))
  }
}

async function uploadFiles(files: File[]) {
  for (const file of files) {
    const id = Math.random().toString(36).substring(7)
    uploading.value.push({ id, name: file.name, status: 'uploading' })

    try {
      const docType = selectedDocType.value || undefined
      const result = await knowledgeApi.uploadDocument(props.collectionId, file, docType)
      const item = uploading.value.find(u => u.id === id)
      const docStatus = result.document?.status
      if (item) {
        if (result.success && docStatus && !['failed'].includes(docStatus)) {
          item.status = 'completed'
        } else {
          item.status = 'failed'
          item.error = docStatus || 'upload_failed'
        }
      }
      if (result.success && docStatus && !['failed'].includes(docStatus)) {
        emit('uploaded', props.collectionId)
      }
    } catch (e: any) {
      const item = uploading.value.find(u => u.id === id)
      if (item) {
        item.status = 'failed'
        item.error = e.response?.data?.detail || e.message
      }
    }
  }

  // 3 秒后清除完成的项
  setTimeout(() => {
    uploading.value = uploading.value.filter(u => u.status === 'uploading')
  }, 3000)
}

function statusText(item: { status: 'uploading' | 'completed' | 'failed'; error?: string }) {
  if (item.status === 'failed') {
    return t('knowledge.uploadStatus.failed', { message: item.error || '' })
  }
  return t(`knowledge.uploadStatus.${item.status}`)
}
</script>

<style scoped>
.document-uploader {
  margin-bottom: 12px;
}

.uploader-options {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
}

.doc-type-label {
  color: #78716c;
}

.doc-type-select {
  flex: 1;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  background: rgba(255,255,255,0.04);
  color: #d6d3d1;
  font-size: 12px;
}

.drop-zone {
  border: 2px dashed rgba(245, 158, 11, 0.25);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255,255,255,0.02);
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: #d97706;
  background: rgba(217, 119, 6, 0.08);
}

.drop-text .icon {
  font-size: 32px;
  display: block;
  margin-bottom: 8px;
}

.drop-text p {
  margin: 0;
  color: #a8a29e;
  font-size: 14px;
}

.drop-text .hint {
  color: #78716c;
  font-size: 12px;
  margin-top: 4px;
}

.upload-progress {
  margin-top: 8px;
}

.progress-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 13px;
}

.file-name {
  color: #a8a29e;
}

.status {
  color: #78716c;
  font-size: 12px;
}
</style>
