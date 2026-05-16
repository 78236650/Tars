<template>
  <div class="meeting-view">
    <div class="meeting-layout">
      <!-- 左侧：设置 + 上传 + 录音 + 历史列表 -->
      <div class="left-panel">
        <MeetingSettings />
        <AudioUploader @uploaded="onUploaded" />
        <RecordingPanel @done="loadHistory" @saved="onRecordingSaved" />
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
import AudioUploader from '@/components/meeting/AudioUploader.vue'
import MeetingSettings from '@/components/meeting/MeetingSettings.vue'
import RecordingPanel from '@/components/meeting/RecordingPanel.vue'
import TranscriptionList from '@/components/meeting/TranscriptionList.vue'
import TranscriptionDetail from '@/components/meeting/TranscriptionDetail.vue'

const transcriptions = ref<Transcription[]>([])
const selectedId = ref<string>('')
const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)

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
    console.error('加载历史失败:', e)
  }
}

function onUploaded(transcription: Transcription) {
  transcriptions.value.unshift(transcription)
  selectedId.value = transcription.id
}

function onRecordingSaved(data: { id: string; status: string }) {
  loadHistory()
  selectedId.value = data.id
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
    alert('删除失败')
  }
}

onMounted(() => {
  loadHistory()
  // 每 5 秒刷新一次状态（用于 pending/processing 状态的更新）
  refreshTimer.value = setInterval(() => {
    const hasPending = transcriptions.value.some(
      t => t.status === 'pending' || t.status === 'processing'
    )
    if (hasPending) {
      loadHistory()
    }
  }, 5000)
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
