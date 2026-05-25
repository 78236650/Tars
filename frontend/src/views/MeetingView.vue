<template>
  <div class="meeting-view">
    <div class="meeting-layout">
      <!-- 左侧：设置 + 上传 + 录音 + 历史列表 -->
      <div class="left-panel">
        <MeetingSettings />
        <AudioUploader @uploaded="onUploaded" />
        <RecordingPanel
          @done="loadHistory"
          @started="onRecordingStarted"
          @transcript="onRecordingTranscript"
          @saved="onRecordingSaved"
          @failed="onRecordingFailed"
        />
        <TranscriptionList
          :transcriptions="transcriptions"
          :selected-id="selectedId"
          @select="onSelect"
          @delete="onDelete"
        />
      </div>

      <!-- 右侧：详情展示 -->
      <div class="right-panel">
        <TranscriptionDetail
          :transcription="selectedTranscription"
          @refresh="loadHistory"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Transcription } from '@/types'
import { meetingApi } from '@/api'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import AudioUploader from '@/components/meeting/AudioUploader.vue'
import MeetingSettings from '@/components/meeting/MeetingSettings.vue'
import RecordingPanel from '@/components/meeting/RecordingPanel.vue'
import TranscriptionList from '@/components/meeting/TranscriptionList.vue'
import TranscriptionDetail from '@/components/meeting/TranscriptionDetail.vue'

const transcriptions = ref<Transcription[]>([])
const selectedId = ref<string>('')
const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)
const { t } = useI18n()
const toast = useToast()

const selectedTranscription = computed(() => {
  return transcriptions.value.find(t => t.id === selectedId.value) || null
})

async function loadHistory() {
  try {
    const result = await meetingApi.listHistory()
    if (result.success) {
      transcriptions.value = result.transcriptions
    }
  } catch (e) {
    console.error(t('meeting.historyLoadFailed'), e)
  }
}

function onUploaded(transcription: Transcription) {
  transcriptions.value = [
    transcription,
    ...transcriptions.value.filter(t => t.id !== transcription.id),
  ]
  selectedId.value = transcription.id
  void loadHistory()
}

function onRecordingStarted(data: { id: string; status: string }) {
  const placeholder: Transcription = {
    id: data.id,
    user_id: '',
    file_name: t('meeting.liveRecordingName'),
    file_size: null,
    duration: null,
    language: null,
    status: data.status as Transcription['status'],
    transcript: null,
    summary: null,
    key_points: [],
    model_used: null,
    created_at: new Date().toISOString(),
    completed_at: null,
    error_message: null,
    approved_at: null,
    knowledge_doc_id: null,
  }
  transcriptions.value = [placeholder, ...transcriptions.value.filter(t => t.id !== data.id)]
  selectedId.value = data.id
}

function onRecordingTranscript(data: { id: string; full_text: string }) {
  const idx = transcriptions.value.findIndex(t => t.id === data.id)
  if (idx < 0) return
  transcriptions.value[idx] = {
    ...transcriptions.value[idx],
    transcript: data.full_text,
    status: 'processing',
  }
}

function onRecordingSaved(data: { id: string; status: string; summarizing?: boolean }) {
  void loadHistory().then(() => {
    selectedId.value = data.id
    if (data.summarizing) {
      const poll = setInterval(() => {
        void loadHistory().then(() => {
          const row = transcriptions.value.find((t) => t.id === data.id)
          if (row?.summary?.trim() || row?.error_message) {
            clearInterval(poll)
          }
        })
      }, 3000)
      setTimeout(() => clearInterval(poll), 120000)
    }
  })
}

function onRecordingFailed(data: { id: string; status: string; error?: string }) {
  void loadHistory().then(() => {
    selectedId.value = data.id
    if (data.error) toast.error(data.error)
  })
}

function onSelect(item: Transcription) {
  selectedId.value = item.id
}

async function onDelete(id: string) {
  try {
    await meetingApi.delete(id)
    transcriptions.value = transcriptions.value.filter(t => t.id !== id)
    if (selectedId.value === id) {
      selectedId.value = ''
    }
  } catch (e) {
    toast.error(t('meeting.deleteFailed'))
  }
}

onMounted(() => {
  loadHistory()
  // 每 5 秒刷新一次状态（用于 pending/processing 状态的更新）
  refreshTimer.value = setInterval(() => {
    const needsRefresh = transcriptions.value.some(
      (t) =>
        t.status === 'pending' ||
        t.status === 'processing' ||
        (t.status === 'completed' && !!t.transcript?.trim() && !t.summary?.trim())
    )
    if (needsRefresh) {
      void loadHistory()
    }
  }, 3000)
})

onUnmounted(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})
</script>

<style scoped>
.meeting-view {
  height: 100%;
  overflow: hidden;
  background: transparent;
}

.meeting-layout {
  display: flex;
  height: 100%;
  gap: 16px;
  padding: 16px;
}

.left-panel {
  width: 360px;
  min-width: 280px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(20, 17, 15, 0.92);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(245, 158, 11, 0.1);
  overflow-y: auto;
  overflow-x: hidden;
}

.right-panel {
  flex: 1;
  background: rgba(20, 17, 15, 0.92);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(245, 158, 11, 0.1);
  overflow: hidden;
}

@media (max-width: 768px) {
  .meeting-layout {
    flex-direction: column;
  }

  .left-panel {
    width: 100%;
    max-width: none;
    max-height: 45vh;
  }
}
</style>
