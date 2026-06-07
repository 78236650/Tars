<template>
  <div class="transcription-detail">
    <div v-if="!transcription" class="empty-state">
      <BaseIcon icon="lucide:mic" :size="48" class="icon" />
      <p>{{ t('meeting.selectToView') }}</p>
    </div>

    <div v-else class="detail-content">
      <div class="detail-header">
        <h2 class="file-name">{{ transcription.file_name || t('meeting.unknownFile') }}</h2>
        <div class="header-actions">
          <span class="status-badge" :class="transcription.status">
            {{ statusText(transcription.status) }}
          </span>
          <button
            v-if="transcription.status === 'completed' && !hasSummary && transcription.transcript"
            class="action-btn primary"
            @click="generateSummary"
            :disabled="summarizing"
          >
            {{ summarizing ? t('meeting.generating') : t('meeting.generateSummary') }}
          </button>
        </div>
      </div>

      <div class="detail-meta">
        <span v-if="transcription.duration">{{ t('meeting.durationLabel') }}: {{ formatDuration(transcription.duration) }}</span>
        <span v-if="transcription.language">{{ t('meeting.languageLabel') }}: {{ transcription.language }}</span>
        <span v-if="transcription.model_used">{{ t('meeting.modelLabel') }}: {{ transcription.model_used }}</span>
        <span>{{ t('meeting.createdLabel') }}: {{ formatDate(transcription.created_at) }}</span>
      </div>

      <!-- 错误信息 -->
      <div v-if="transcription.error_message" class="error-box">
        <strong>{{ t('meeting.errorLabel') }}:</strong> {{ transcription.error_message }}
      </div>

      <!-- 原音频播放 -->
      <div v-if="transcription.has_audio || audioUrl || audioLoading" class="section audio-section">
        <h3 class="section-title"><BaseIcon icon="lucide:volume-2" :size="16" /> {{ t('meeting.originalAudio') }}</h3>
        <p v-if="audioLoading" class="audio-hint">{{ t('meeting.audioLoading') }}</p>
        <audio
          v-else-if="audioUrl"
          class="audio-player"
          controls
          preload="metadata"
          :src="audioUrl"
        />
        <p v-else class="audio-hint">{{ t('meeting.audioUnavailable') }}</p>
      </div>
      <p v-else-if="showAudioMissingHint" class="audio-missing-hint">{{ t('meeting.audioUnavailable') }}</p>

      <!-- 摘要区域 -->
      <div v-if="normalizedSummary || editing" class="section summary-section">
        <div class="summary-card">
          <div class="summary-card-header">
            <div>
              <h3 class="section-title"><BaseIcon icon="lucide:clipboard" :size="16" /> {{ t('meeting.summaryTitle') }}</h3>
              <p class="summary-source-hint">{{ t('meeting.summarySource') }}</p>
            </div>
            <div class="summary-header-actions">
              <button
                v-if="!editing && transcription.summary && !transcription.approved_at"
                class="edit-btn"
                @click="startEdit"
              >
                <BaseIcon icon="lucide:pencil" :size="14" /> {{ t('meeting.editSummary') }}
              </button>
              <span v-if="transcription.approved_at" class="approved-badge"><BaseIcon icon="lucide:check-circle" :size="16" class="text-emerald-400" /> {{ t('meeting.approved') }}</span>
            </div>
          </div>

          <textarea
            v-if="editing"
            v-model="editSummary"
            class="edit-textarea"
            rows="14"
            :placeholder="t('meeting.summaryEditPlaceholder')"
          />

          <template v-else-if="normalizedSummary">
            <nav v-if="summarySections.length > 1" class="summary-nav" aria-label="summary outline">
              <span class="summary-nav-label">{{ t('meeting.summaryNav') }}</span>
              <a
                v-for="sec in summarySections"
                :key="sec.id"
                :href="`#summary-${sec.id}`"
                class="summary-nav-link"
              >{{ sec.title }}</a>
            </nav>
            <div
              class="summary-prose markdown-body"
              v-html="renderedSummaryHtml"
            ></div>
          </template>
        </div>
      </div>

      <!-- 关键要点（摘要已含该章节时隐藏，避免重复） -->
      <div
        v-if="showStandaloneKeyPoints || editing"
        class="section key-points-section"
      >
        <h3 class="section-title"><BaseIcon icon="lucide:target" :size="16" /> {{ t('meeting.keyPointsTitle') }}</h3>
        <textarea v-if="editing" v-model="editKeyPoints" class="edit-textarea" rows="4" :placeholder="t('meeting.keyPointsPlaceholder')"></textarea>
        <ul v-else class="key-points">
          <li v-for="(point, i) in transcription.key_points" :key="i">{{ point }}</li>
        </ul>
      </div>

      <!-- 编辑操作栏 -->
      <div v-if="editing" class="edit-actions">
        <button class="action-btn primary" @click="saveEdit">{{ t('meeting.saveChanges') }}</button>
        <button class="action-btn" @click="cancelEdit">{{ t('common.cancel') }}</button>
      </div>

      <!-- 确认入库按钮 / 成功状态 -->
      <div v-if="transcription.summary && !editing" class="approve-section">
        <div v-if="transcription.approved_at || approveSuccess" class="approve-done">
          <BaseIcon icon="lucide:check-circle" :size="16" class="text-emerald-400" /> {{ t('meeting.approveDone') }}
        </div>
        <button v-else class="action-btn approve" @click="approveToKnowledge" :disabled="approving">
          <template v-if="approving">{{ t('meeting.approving') }}</template>
          <template v-else><BaseIcon icon="lucide:download" :size="14" /> {{ t('meeting.approveToKnowledge') }}</template>
        </button>
      </div>

      <!-- 转写文本 -->
      <div v-if="transcription.transcript" class="section transcript-section">
        <button type="button" class="transcript-toggle" @click="showTranscript = !showTranscript">
          <span><BaseIcon icon="lucide:file-text" :size="14" /> {{ t('meeting.transcriptTitle') }}</span>
          <span class="transcript-toggle-hint">{{ showTranscript ? t('meeting.hideTranscript') : t('meeting.showTranscript') }}</span>
        </button>
        <div v-show="showTranscript" class="transcript-text">{{ transcription.transcript }}</div>
      </div>

      <!-- 待处理 / 摘要生成中 -->
      <div
        v-if="transcription.status === 'pending' || transcription.status === 'processing' || summarizing"
        class="pending-box"
      >
        <div class="spinner"></div>
        <p>{{ summarizing ? t('meeting.summaryGenerating') : t('meeting.pendingMessage') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import type { Transcription } from '@/types'
import { meetingApi } from '@/api'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'
import { renderMarkdown } from '@/utils/markdown'
import BaseIcon from '@/components/common/BaseIcon.vue'
import {
  extractSummarySections,
  normalizeMeetingSummary,
  summaryHasKeyPointsSection,
} from '@/utils/meetingSummary'

interface Props {
  transcription: Transcription | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  refresh: []
}>()

const summarizing = ref(false)
const autoSummaryAttempted = ref<Set<string>>(new Set())
const audioUrl = ref('')
const audioLoading = ref(false)
const audioChecked = ref(false)

const hasSummary = computed(() => {
  const raw = props.transcription?.summary
  return Boolean(raw && String(raw).trim())
})

const showAudioMissingHint = computed(() => {
  if (!props.transcription) return false
  if (props.transcription.has_audio) return false
  return audioChecked.value && !audioUrl.value && !audioLoading.value
})

function revokeAudioUrl() {
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = ''
  }
}

async function loadAudio() {
  if (!props.transcription?.id) return
  revokeAudioUrl()
  audioLoading.value = false
  audioChecked.value = false
  if (props.transcription.has_audio === false) {
    audioChecked.value = true
    return
  }
  audioLoading.value = true
  try {
    const blob = await meetingApi.fetchAudio(props.transcription.id)
    if (blob.size > 0) {
      audioUrl.value = URL.createObjectURL(blob)
    }
  } catch {
    /* 无音频或旧记录未保存文件 */
  } finally {
    audioLoading.value = false
    audioChecked.value = true
  }
}
const editing = ref(false)
const editSummary = ref('')
const editKeyPoints = ref('')
const approving = ref(false)
const approveSuccess = ref(false)
const showTranscript = ref(false)
const { t, locale } = useI18n()
const toast = useToast()

watch(
  () => [props.transcription?.status, props.transcription?.transcript] as const,
  ([status, transcript]) => {
    if (status === 'processing' && transcript) {
      showTranscript.value = true
    }
  },
)

const normalizedSummary = computed(() =>
  normalizeMeetingSummary(props.transcription?.summary),
)

const summarySections = computed(() =>
  extractSummarySections(normalizedSummary.value),
)

const showStandaloneKeyPoints = computed(() => {
  if (editing.value) return true
  const points = props.transcription?.key_points
  if (!points?.length) return false
  if (normalizedSummary.value && summaryHasKeyPointsSection(normalizedSummary.value)) {
    return false
  }
  return true
})

function injectHeadingAnchors(html: string): string {
  const sections = summarySections.value
  let index = 0
  return html.replace(/<h2>/g, () => {
    const id = sections[index]?.id ?? `section-${index}`
    index += 1
    return `<h2 id="summary-${id}">`
  })
}

const renderedSummaryHtml = computed(() => {
  const md = normalizedSummary.value
  if (!md) return ''
  return injectHeadingAnchors(renderMarkdown(md))
})

async function generateSummary() {
  if (!props.transcription) return
  if (!props.transcription.transcript?.trim()) {
    toast.error(t('meeting.summaryNeedsTranscript'))
    return
  }
  summarizing.value = true
  try {
    const res = await meetingApi.summarize(props.transcription.id)
    if (!res.transcription?.summary?.trim()) {
      toast.error(t('meeting.summaryGenerateFailed'))
      return
    }
    emit('refresh')
    toast.success(t('meeting.summaryGenerateSuccess'))
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('meeting.summaryGenerateFailed')))
  } finally {
    summarizing.value = false
  }
}

watch(
  () => props.transcription?.id,
  () => {
    autoSummaryAttempted.value = new Set()
    void loadAudio()
  },
)

watch(
  () => props.transcription?.has_audio,
  () => {
    void loadAudio()
  },
)

onBeforeUnmount(() => {
  revokeAudioUrl()
})

watch(
  () => [
    props.transcription?.id,
    props.transcription?.status,
    props.transcription?.transcript,
    hasSummary.value,
  ] as const,
  ([id, status, transcript, hasSum]) => {
    if (!id || status !== 'completed' || !transcript?.trim() || hasSum) return
    if (autoSummaryAttempted.value.has(id) || summarizing.value) return
    autoSummaryAttempted.value.add(id)
    void generateSummary()
  },
)

function startEdit() {
  if (!props.transcription) return
  editSummary.value = normalizedSummary.value || props.transcription.summary || ''
  const kp = props.transcription.key_points
  editKeyPoints.value = Array.isArray(kp) ? kp.join('\n') : ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit(): Promise<boolean> {
  if (!props.transcription) return false
  try {
    const keyPoints = editKeyPoints.value.split('\n').map(s => s.trim()).filter(Boolean)
    await meetingApi.updateSummary(props.transcription.id, editSummary.value, keyPoints)
    editing.value = false
    emit('refresh')
    return true
  } catch (e: any) {
    toast.error(getErrorDetail(e, t('meeting.saveSummaryFailed')))
    return false
  }
}

async function approveToKnowledge() {
  if (!props.transcription) return
  const summary = (editing.value ? editSummary.value : normalizedSummary.value || props.transcription.summary || '').trim()
  const kpRaw = editing.value
    ? editKeyPoints.value
    : (Array.isArray(props.transcription.key_points)
      ? props.transcription.key_points.join('\n')
      : '')
  const kp = kpRaw.split('\n').map(s => s.trim()).filter(Boolean)
  if (!summary) {
    toast.error(t('meeting.summaryRequiredForApprove'))
    return
  }
  if (editing.value) {
    const saved = await saveEdit()
    if (!saved) return
  }
  approving.value = true
  try {
    await meetingApi.approveToKnowledge(props.transcription.id, summary, kp)
    approveSuccess.value = true
    emit('refresh')
  } catch (e: any) {
    toast.error(getErrorDetail(e, t('meeting.approveFailed')))
  } finally {
    approving.value = false
  }
}

function statusText(status: string): string {
  return t(`meeting.status.${status}`)
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
  return d.toLocaleString(locale.value === 'zh' ? 'zh-CN' : 'en-US')
}
</script>

<style scoped>
.transcription-detail {
  height: 100%;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #78716c;
  text-align: center;
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.detail-content {
  padding: 20px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.file-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #e7e5e4;
  word-break: break-all;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.status-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 500;
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

.action-btn {
  padding: 5px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn.primary {
  background: #d97706;
  color: #0c0b09;
}

.action-btn.primary:hover:not(:disabled) {
  background: #f59e0b;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.detail-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  font-size: 12px;
  color: #78716c;
}

.section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #d6d3d1;
}

.summary-card {
  border: 1px solid rgba(245, 158, 11, 0.18);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02));
  padding: 18px 20px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.summary-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(245, 158, 11, 0.1);
}

.summary-source-hint {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: #78716c;
}

.summary-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.summary-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(245, 158, 11, 0.08);
}

.summary-nav-label {
  font-size: 11px;
  font-weight: 600;
  color: #a8a29e;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.summary-nav-link {
  font-size: 12px;
  color: #fbbf24;
  text-decoration: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.1);
  transition: background 0.15s;
}

.summary-nav-link:hover {
  background: rgba(217, 119, 6, 0.2);
  color: #fde68a;
}

.summary-prose {
  font-size: 14px;
  line-height: 1.85;
  color: #d6d3d1;
  max-width: 72ch;
}

.summary-prose :deep(h1) {
  font-size: 1.25rem;
  font-weight: 700;
  color: #fafaf9;
  margin: 0 0 0.75rem;
}

.summary-prose :deep(h2) {
  font-size: 1rem;
  font-weight: 600;
  color: #fef3c7;
  margin: 1.5rem 0 0.65rem;
  padding: 0.35rem 0 0.35rem 0.65rem;
  border-left: 3px solid rgba(217, 119, 6, 0.65);
  scroll-margin-top: 80px;
}

.summary-prose :deep(h2:first-child) {
  margin-top: 0;
}

.summary-prose :deep(h3) {
  font-size: 0.92rem;
  font-weight: 600;
  color: #e7e5e4;
  margin: 1rem 0 0.45rem;
}

.summary-prose :deep(p) {
  margin: 0 0 0.75rem;
}

.summary-prose :deep(ul),
.summary-prose :deep(ol) {
  padding-left: 1.25rem;
  margin: 0 0 0.85rem;
}

.summary-prose :deep(li) {
  margin-bottom: 0.35rem;
}

.summary-prose :deep(li::marker) {
  color: #d97706;
}

.summary-prose :deep(strong) {
  color: #fafaf9;
  font-weight: 600;
}

.summary-prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.85rem 0 1rem;
  font-size: 13px;
  display: block;
  overflow-x: auto;
}

.summary-prose :deep(th),
.summary-prose :deep(td) {
  border: 1px solid rgba(245, 158, 11, 0.15);
  padding: 0.45rem 0.65rem;
  text-align: left;
  white-space: nowrap;
}

.summary-prose :deep(th) {
  background: rgba(217, 119, 6, 0.12);
  color: #fef3c7;
}

.summary-prose :deep(blockquote) {
  border-left: 3px solid rgba(217, 119, 6, 0.45);
  padding: 0.35rem 0 0.35rem 0.85rem;
  margin: 0.75rem 0;
  color: #a8a29e;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 0 8px 8px 0;
}

.summary-prose :deep(hr) {
  border: none;
  border-top: 1px solid rgba(245, 158, 11, 0.12);
  margin: 1.25rem 0;
}

.summary-prose :deep(code) {
  background: rgba(255, 255, 255, 0.06);
  color: #fbbf24;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.85em;
}

.summary-prose :deep(pre) {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  margin: 0.75rem 0;
}

.key-points-section {
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(245, 158, 11, 0.08);
}

.section-body {
  font-size: 14px;
  line-height: 1.7;
  color: #a8a29e;
}

.section-body.markdown-body :deep(h1) {
  font-size: 1.2rem;
  font-weight: 700;
  color: #e7e5e4;
  margin: 1.25rem 0 0.6rem;
}

.section-body.markdown-body :deep(h2) {
  font-size: 1.05rem;
  font-weight: 600;
  color: #f5f5f4;
  margin: 1.1rem 0 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid rgba(245, 158, 11, 0.12);
}

.section-body.markdown-body :deep(h3) {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e7e5e4;
  margin: 0.9rem 0 0.4rem;
}

.section-body.markdown-body :deep(p) {
  margin-bottom: 0.65rem;
}

.section-body.markdown-body :deep(ul),
.section-body.markdown-body :deep(ol) {
  padding-left: 1.4rem;
  margin-bottom: 0.65rem;
}

.section-body.markdown-body :deep(li) {
  margin-bottom: 0.25rem;
}

.section-body.markdown-body :deep(strong) {
  color: #f5f5f4;
  font-weight: 600;
}

.section-body.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
  font-size: 13px;
}

.section-body.markdown-body :deep(th),
.section-body.markdown-body :deep(td) {
  border: 1px solid rgba(245, 158, 11, 0.15);
  padding: 0.4rem 0.6rem;
  text-align: left;
}

.section-body.markdown-body :deep(th) {
  background: rgba(255, 255, 255, 0.04);
  color: #e7e5e4;
}

.section-body.markdown-body :deep(blockquote) {
  border-left: 3px solid rgba(217, 119, 6, 0.45);
  padding-left: 0.75rem;
  margin: 0.65rem 0;
  color: #a8a29e;
}

.section-body.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(245, 158, 11, 0.12);
  margin: 1rem 0;
}

.section-body.markdown-body :deep(code) {
  background: rgba(255, 255, 255, 0.06);
  color: #fbbf24;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  font-size: 0.85em;
}

.section-body.markdown-body :deep(pre) {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  margin: 0.75rem 0;
}

.section-body.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #d6d3d1;
}

.key-points {
  margin: 0;
  padding-left: 20px;
}

.key-points li {
  font-size: 14px;
  line-height: 1.7;
  color: #d6d3d1;
  margin-bottom: 6px;
  padding-left: 4px;
}

.transcript-section {
  margin-top: 8px;
}

.transcript-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: #d6d3d1;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.transcript-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
}

.transcript-toggle-hint {
  font-size: 11px;
  color: #78716c;
}

.transcript-text {
  font-size: 14px;
  line-height: 1.8;
  color: #a8a29e;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  word-break: break-word;
}

.error-box {
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 13px;
  margin-bottom: 16px;
}

.audio-section {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 8px;
}

.audio-player {
  width: 100%;
  margin-top: 8px;
}

.audio-hint,
.audio-missing-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #78716c;
}

.pending-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #78716c;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(245, 158, 11, 0.15);
  border-top-color: #d97706;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.edit-btn { border: none; background: none; cursor: pointer; font-size: 13px; margin-left: 8px; }
.edit-btn:hover { opacity: 0.7; }
.approved-badge { font-size: 12px; margin-left: 8px; color: #34d399; }
.edit-textarea { width: 100%; padding: 10px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px; font-size: 14px; line-height: 1.6; resize: vertical; font-family: inherit; background: rgba(255,255,255,0.04); color: #e7e5e4; }
.edit-actions { display: flex; gap: 8px; margin-bottom: 16px; }
.approve-section { margin-bottom: 16px; }
.approve-done { padding: 10px 16px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; color: #34d399; font-weight: 500; font-size: 14px; }
.action-btn.approve { background: #059669; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; }
.action-btn.approve:hover:not(:disabled) { background: #047857; }
.action-btn.approve:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
