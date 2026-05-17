<template>
  <div class="recording-panel">
    <!-- idle 状态：开始录音按钮 -->
    <div v-if="state === 'idle'" class="idle-state">
      <button class="start-btn" @click="startRecording">
        <span class="btn-icon">🎤</span>
        {{ t('meeting.startRecording') }}
      </button>
    </div>

    <!-- recording 状态：录音中 + 实时转写 -->
    <div v-else-if="state === 'recording'" class="recording-state">
      <div class="recording-header">
        <span class="recording-indicator">🔴 {{ t('meeting.recordingNow') }}</span>
        <span class="recording-time">{{ formatTime(seconds) }}</span>
        <button class="stop-btn" @click="stopRecording">{{ t('meeting.stopAndSave') }}</button>
      </div>
      <div class="transcript-area">
        <p v-if="transcripts.length === 0" class="placeholder">{{ t('meeting.waitingTranscript') }}</p>
        <p v-for="(text, i) in transcripts" :key="i">{{ text }}</p>
      </div>
      <button class="cancel-btn" @click="cancelRecording">{{ t('meeting.cancelRecording') }}</button>
    </div>

    <!-- completed 状态：录音完成 -->
    <div v-else-if="state === 'completed'" class="completed-state">
      <div class="completed-header">
        <span>✅ {{ t('meeting.recordingCompleted') }}</span>
        <span class="duration">{{ t('meeting.durationLabel') }}: {{ formatTime(seconds) }}</span>
      </div>
      <div class="transcript-area">
        <p v-for="(text, i) in transcripts" :key="i">{{ text }}</p>
      </div>
      <div class="completed-actions">
        <button class="action-btn primary" @click="resetAndDone">{{ t('meeting.backToList') }}</button>
      </div>
    </div>

    <div v-if="errorMsg" class="error-message">{{ errorMsg }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { useI18n } from '@/i18n'

const emit = defineEmits<{
  done: []
  saved: [transcription: { id: string; status: string }]
}>()

type State = 'idle' | 'recording' | 'completed'

const state = ref<State>('idle')
const seconds = ref(0)
const transcripts = ref<string[]>([])
const errorMsg = ref('')
const { t, locale } = useI18n()

let mediaRecorder: MediaRecorder | null = null
let timer: ReturnType<typeof setInterval> | null = null
let ws: WebSocket | null = null
let chunkIndex = 0

function formatTime(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  if (locale.value === 'zh') {
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
}

async function startRecording() {
  errorMsg.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/api/meeting/ws/record`)

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'transcript' && msg.text) {
        transcripts.value.push(msg.text)
      } else if (msg.type === 'done') {
        state.value = 'completed'
        emit('saved', { id: msg.transcription_id, status: 'completed' })
      } else if (msg.type === 'error') {
        errorMsg.value = msg.message
      }
    }

    ws.onclose = () => {
      if (state.value === 'recording') {
        state.value = 'completed'
      }
    }

    await new Promise<void>((resolve, reject) => {
      ws!.onopen = () => resolve()
      ws!.onerror = () => reject(new Error(t('meeting.websocketFailed')))
    })

    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    chunkIndex = 0
    transcripts.value = []
    seconds.value = 0

    mediaRecorder.ondataavailable = async (e) => {
      if (e.data.size > 0 && ws?.readyState === WebSocket.OPEN) {
        const buffer = await e.data.arrayBuffer()
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buffer)))
        ws.send(JSON.stringify({ type: 'audio', data: b64, index: chunkIndex++ }))
      }
    }

    mediaRecorder.start(5000)
    state.value = 'recording'
    timer = setInterval(() => { seconds.value++ }, 1000)

  } catch (e: any) {
    errorMsg.value = e.message || t('meeting.microphoneDenied')
  }
}

function stopRecording() {
  if (seconds.value < 5) {
    errorMsg.value = t('meeting.recordingTooShort')
    cancelRecording()
    setTimeout(() => { errorMsg.value = '' }, 3000)
    return
  }
  if (timer) { clearInterval(timer); timer = null }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    mediaRecorder.stream.getTracks().forEach(t => t.stop())
  }
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'stop' }))
  }
  state.value = 'completed'
  mediaRecorder = null
}

function cancelRecording() {
  if (timer) { clearInterval(timer); timer = null }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    mediaRecorder.stream.getTracks().forEach(t => t.stop())
  }
  if (ws) { ws.close(); ws = null }
  mediaRecorder = null
  state.value = 'idle'
  transcripts.value = []
  seconds.value = 0
}

function resetAndDone() {
  state.value = 'idle'
  transcripts.value = []
  seconds.value = 0
  emit('done')
}

onBeforeUnmount(() => {
  if (state.value === 'recording') cancelRecording()
})
</script>

<style scoped>
.recording-panel { margin-bottom: 16px; }

.idle-state { text-align: center; padding: 20px; }
.start-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border: 2px solid #d97706; border-radius: 12px;
  background: rgba(217, 119, 6, 0.08); color: #fbbf24; font-size: 16px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.start-btn:hover { background: rgba(217, 119, 6, 0.16); }
.btn-icon { font-size: 20px; }

.recording-state { padding: 16px; background: rgba(20,17,15,0.92); border: 1px solid rgba(245, 158, 11, 0.12); border-radius: 12px; }
.recording-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.recording-indicator { color: #fbbf24; font-weight: 500; animation: pulse 1.5s infinite; }
.recording-time { font-variant-numeric: tabular-nums; color: #a8a29e; font-size: 14px; }
.stop-btn {
  margin-left: auto; padding: 6px 14px; border: 1px solid #d97706; border-radius: 6px;
  background: #d97706; color: #0c0b09; font-size: 13px; font-weight: 500; cursor: pointer;
}
.stop-btn:hover { background: #f59e0b; }

.transcript-area {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(245, 158, 11, 0.1); border-radius: 8px;
  padding: 12px; max-height: 240px; overflow-y: auto; min-height: 80px;
}
.transcript-area p { margin: 4px 0; font-size: 14px; color: #a8a29e; line-height: 1.6; }
.placeholder { color: #78716c; font-style: italic; }

.cancel-btn {
  margin-top: 8px; padding: 4px 12px; border: none; background: none;
  color: #78716c; font-size: 12px; cursor: pointer; text-decoration: underline;
}

.completed-state { padding: 16px; background: rgba(20,17,15,0.92); border: 1px solid rgba(245, 158, 11, 0.1); border-radius: 12px; }
.completed-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-weight: 500; color: #d6d3d1; }
.duration { font-size: 13px; color: #78716c; font-weight: normal; }
.completed-actions { margin-top: 12px; display: flex; gap: 8px; }
.action-btn {
  padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.06); color: #d6d3d1;
}
.action-btn.primary { background: #d97706; color: #0c0b09; border-color: #d97706; font-weight: 500; }
.action-btn.primary:hover { background: #f59e0b; }

.error-message { margin-top: 8px; padding: 8px 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 6px; color: #fca5a5; font-size: 13px; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
