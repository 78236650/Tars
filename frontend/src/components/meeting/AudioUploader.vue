<template>
  <div class="audio-uploader">
    <div
      class="drop-zone"
      :class="{ dragging: isDragging, uploading: isUploading }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg,.flac,.wma"
        style="display: none"
        @change="handleFileSelect"
      />
      <div class="drop-content">
        <BaseIcon icon="lucide:folder-open" :size="48" class="icon" />
        <p class="title">{{ isUploading ? t('meeting.uploading') : t('meeting.uploadPrompt') }}</p>
        <p class="hint">{{ t('meeting.uploadHint') }}</p>
        <div v-if="isUploading" class="progress-bar">
          <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
        </div>
      </div>
    </div>
    <div v-if="uploadError" class="error-message">{{ uploadError }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { meetingApi } from '@/api'
import { meetingAsrLanguageForApi } from '@/composables/useMeetingAsrLanguage'
import { useI18n } from '@/i18n'
import BaseIcon from '@/components/common/BaseIcon.vue'

const emit = defineEmits<{ uploaded: [transcription: any] }>()

const fileInput = ref<HTMLInputElement>()
const isDragging = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const { t } = useI18n()

const SUPPORTED_FORMATS = ['.mp3', '.wav', '.m4a', '.mp4', '.webm', '.ogg', '.flac', '.wma']

function triggerFileInput() {
  if (isUploading.value) return
  fileInput.value?.click()
}

function validateFile(file: File): string | null {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!SUPPORTED_FORMATS.includes(ext)) return t('meeting.unsupportedFormat', { ext })
  if (file.size > 50 * 1024 * 1024) return t('meeting.fileTooLarge')
  return null
}

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) uploadFile(files[0])
}

function handleFileSelect(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files && files.length > 0) uploadFile(files[0])
}

async function uploadFile(file: File) {
  const error = validateFile(file)
  if (error) { uploadError.value = error; setTimeout(() => { uploadError.value = '' }, 5000); return }
  isUploading.value = true
  uploadProgress.value = 30
  uploadError.value = ''
  try {
    uploadProgress.value = 60
    const result = await meetingApi.upload(file, meetingAsrLanguageForApi())
    uploadProgress.value = 100
    if (result.success) emit('uploaded', result.transcription)
    else uploadError.value = t('meeting.uploadFailed')
  } catch (e: any) {
    uploadError.value = e.response?.data?.detail || e.message || t('meeting.uploadFailed')
  } finally {
    setTimeout(() => { isUploading.value = false; uploadProgress.value = 0 }, 500)
  }
}
</script>

<style scoped>
.audio-uploader { margin-bottom: 16px; }
.drop-zone { border: 2px dashed #d1d5db; border-radius: 12px; padding: 24px; text-align: center; cursor: pointer; transition: all 0.2s; background: #fafafa; }
.drop-zone:hover:not(.uploading) { border-color: #3b82f6; background: #eff6ff; }
.drop-zone.dragging { border-color: #3b82f6; background: #eff6ff; }
.drop-zone.uploading { cursor: not-allowed; opacity: 0.8; }
.drop-content .icon { font-size: 36px; display: block; margin-bottom: 8px; }
.drop-content .title { margin: 0 0 6px; color: #374151; font-size: 14px; font-weight: 500; }
.drop-content .hint { margin: 0; color: #9ca3af; font-size: 12px; }
.progress-bar { margin-top: 12px; height: 5px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: #3b82f6; border-radius: 3px; transition: width 0.3s; }
.error-message { margin-top: 8px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; color: #dc2626; font-size: 13px; }
</style>
