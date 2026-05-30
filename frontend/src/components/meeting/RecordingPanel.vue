<template>
  <div class="recording-panel">
    <div v-if="state === 'idle'" class="idle-state">
      <button class="start-btn" @click="startRecording">
        <BaseIcon icon="lucide:mic" :size="20" />
        {{ t('meeting.startRecording') }}
      </button>
    </div>

    <div v-else-if="state === 'recording'" class="recording-state">
      <div class="recording-header">
        <span class="recording-indicator"><BaseIcon icon="lucide:circle" :size="12" class="text-red-500 fill-red-500" /> {{ t('meeting.recordingNow') }}</span>
        <span class="recording-time">{{ formatTime(seconds) }}</span>
        <button class="stop-btn" @click="stopRecording">{{ t('meeting.stopAndSave') }}</button>
      </div>
      <div class="transcript-area">
        <p v-if="!displayText" class="placeholder">{{ t('meeting.recordingHint') }}</p>
        <p v-else>{{ displayText }}</p>
      </div>
      <button class="cancel-btn" @click="cancelRecording">{{ t('meeting.cancelRecording') }}</button>
    </div>

    <div v-else-if="state === 'transcribing'" class="recording-state">
      <div class="recording-header">
        <span class="recording-indicator"><BaseIcon icon="lucide:hourglass" :size="16" /> {{ t('meeting.transcribingNow') }}</span>
        <span class="recording-time">{{ formatTime(seconds) }}</span>
      </div>
      <div class="transcript-area">
        <p v-if="displayText">{{ displayText }}</p>
        <p v-else class="placeholder">{{ t('meeting.transcribingHint') }}</p>
      </div>
    </div>

    <div v-else-if="state === 'completed'" class="completed-state">
      <div class="completed-header">
        <span><BaseIcon icon="lucide:check-circle" :size="16" class="text-emerald-400" /> {{ t('meeting.recordingCompleted') }}</span>
        <span class="duration">{{ t('meeting.durationLabel') }}: {{ formatTime(seconds) }}</span>
      </div>
      <div class="transcript-area">
        <p>{{ displayText || t('meeting.noTranscriptText') }}</p>
      </div>
      <div class="completed-actions">
        <button class="action-btn primary" @click="resetAndDone">{{ t('meeting.backToList') }}</button>
      </div>
    </div>

    <div v-if="errorMsg" class="error-message">{{ errorMsg }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useI18n } from '@/i18n'
import { resolveMeetingWebSocketUrl } from '@/utils/websocket'
import BaseIcon from '@/components/common/BaseIcon.vue'

const emit = defineEmits<{
  done: []
  started: [transcription: { id: string; status: string }]
  transcript: [payload: { id: string; full_text: string }]
  saved: [transcription: { id: string; status: string; summarizing?: boolean }]
  failed: [transcription: { id: string; status: string; error?: string }]
}>()

type State = 'idle' | 'recording' | 'transcribing' | 'completed'

const state = ref<State>('idle')
const seconds = ref(0)
const liveText = ref('')
const transcriptionId = ref('')
const errorMsg = ref('')
const { t, locale } = useI18n()

const displayText = computed(() => liveText.value.trim())

let mediaRecorder: MediaRecorder | null = null
let timer: ReturnType<typeof setInterval> | null = null
let ws: WebSocket | null = null
let chunkIndex = 0
let stopping = false
let stopSent = false
let audioSendChain = Promise.resolve()

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}

function sendStopMessage() {
  if (stopSent || ws?.readyState !== WebSocket.OPEN) return
  stopSent = true
  state.value = 'transcribing'
  ws.send(JSON.stringify({ type: 'stop' }))
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
}

function appendTranscript(text: string, fullText?: string) {
  if (fullText) {
    liveText.value = fullText
  } else {
    const chunk = (text || '').trim()
    if (!chunk) return
    liveText.value = liveText.value ? `${liveText.value}\n${chunk}` : chunk
  }
  if (transcriptionId.value) {
    emit('transcript', { id: transcriptionId.value, full_text: liveText.value })
  }
}

async function startRecording() {
  errorMsg.value = ''
  stopping = false
  stopSent = false
  audioSendChain = Promise.resolve()
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    ws = new WebSocket(resolveMeetingWebSocketUrl())

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'started' && msg.transcription_id) {
        transcriptionId.value = msg.transcription_id
        emit('started', { id: msg.transcription_id, status: 'processing' })
      } else if (msg.type === 'transcript') {
        appendTranscript(msg.text, msg.full_text)
      } else if (msg.type === 'status' && msg.phase === 'transcribing') {
        state.value = 'transcribing'
      } else if (msg.type === 'done') {
        if (msg.full_text) {
          liveText.value = msg.full_text
          if (transcriptionId.value) {
            emit('transcript', { id: transcriptionId.value, full_text: msg.full_text })
          }
        }
        state.value = msg.summarizing ? 'transcribing' : 'completed'
        emit('saved', {
          id: msg.transcription_id || transcriptionId.value,
          status: 'completed',
          summarizing: Boolean(msg.summarizing),
        })
      } else if (msg.type === 'error') {
        errorMsg.value = msg.message
        if (msg.transcription_id) {
          emit('failed', { id: msg.transcription_id, status: 'failed', error: msg.message })
        }
        state.value = 'idle'
      }
    }

    ws.onclose = () => {
      if (state.value === 'recording' || state.value === 'transcribing') {
        if (!errorMsg.value && !liveText.value) {
          errorMsg.value = t('meeting.websocketClosed')
        }
        if (state.value === 'transcribing' && transcriptionId.value) {
          emit('saved', { id: transcriptionId.value, status: 'processing' })
        }
        if (state.value !== 'completed') state.value = liveText.value ? 'completed' : 'idle'
      }
    }

    await new Promise<void>((resolve, reject) => {
      ws!.onopen = () => resolve()
      ws!.onerror = () => reject(new Error(t('meeting.websocketFailed')))
    })

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm'
    mediaRecorder = new MediaRecorder(stream, { mimeType })
    chunkIndex = 0
    liveText.value = ''
    transcriptionId.value = ''
    seconds.value = 0

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size <= 0) {
        if (stopping) {
          audioSendChain = audioSendChain.then(() => sendStopMessage())
        }
        return
      }
      audioSendChain = audioSendChain.then(async () => {
        if (ws?.readyState !== WebSocket.OPEN) return
        const buffer = await e.data.arrayBuffer()
        const b64 = arrayBufferToBase64(buffer)
        ws!.send(JSON.stringify({ type: 'audio', data: b64, index: chunkIndex++ }))
      }).then(() => {
        if (stopping) sendStopMessage()
      })
    }

    mediaRecorder.onstop = () => {
      mediaRecorder?.stream.getTracks().forEach(track => track.stop())
      audioSendChain = audioSendChain.then(() => {
        if (stopping) sendStopMessage()
      })
    }

    mediaRecorder.start(5000)
    state.value = 'recording'
    timer = setInterval(() => { seconds.value++ }, 1000)
  } catch (e: any) {
    errorMsg.value = e.message || t('meeting.microphoneDenied')
  }
}

function stopRecording() {
  if (stopping) return
  if (seconds.value < 5) {
    errorMsg.value = t('meeting.recordingTooShort')
    cancelRecording()
    setTimeout(() => { errorMsg.value = '' }, 3000)
    return
  }
  stopping = true
  if (timer) { clearInterval(timer); timer = null }

  const recorder = mediaRecorder
  mediaRecorder = null

  if (recorder && recorder.state !== 'inactive') {
    recorder.stop()
  } else {
    audioSendChain = audioSendChain.then(() => sendStopMessage())
  }
}

async function cancelRecording() {
  stopping = true
  if (timer) { clearInterval(timer); timer = null }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    mediaRecorder.stream.getTracks().forEach(track => track.stop())
  }
  if (ws) { ws.close(); ws = null }
  mediaRecorder = null
  state.value = 'idle'
  liveText.value = ''
  transcriptionId.value = ''
  seconds.value = 0
  stopping = false
  stopSent = false
  audioSendChain = Promise.resolve()
}

function resetAndDone() {
  state.value = 'idle'
  liveText.value = ''
  transcriptionId.value = ''
  seconds.value = 0
  stopping = false
  emit('done')
}

onBeforeUnmount(() => {
  if (state.value === 'recording' || state.value === 'transcribing') cancelRecording()
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
.transcript-area p { margin: 4px 0; font-size: 14px; color: #a8a29e; line-height: 1.6; white-space: pre-wrap; }
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
