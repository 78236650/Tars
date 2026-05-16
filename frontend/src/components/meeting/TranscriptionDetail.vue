<template>
  <div class="transcription-detail">
    <div v-if="!transcription" class="empty-state">
      <span class="icon">🎙️</span>
      <p>选择一条转录记录查看详情</p>
    </div>

    <div v-else class="detail-content">
      <div class="detail-header">
        <h2 class="file-name">{{ transcription.file_name || '未知文件' }}</h2>
        <div class="header-actions">
          <span class="status-badge" :class="transcription.status">
            {{ statusText(transcription.status) }}
          </span>
          <button
            v-if="transcription.status === 'completed' && !transcription.summary"
            class="action-btn primary"
            @click="generateSummary"
            :disabled="summarizing"
          >
            {{ summarizing ? '生成中...' : '生成摘要' }}
          </button>
        </div>
      </div>

      <div class="detail-meta">
        <span v-if="transcription.duration">时长: {{ formatDuration(transcription.duration) }}</span>
        <span v-if="transcription.language">语言: {{ transcription.language }}</span>
        <span v-if="transcription.model_used">模型: {{ transcription.model_used }}</span>
        <span>创建: {{ formatDate(transcription.created_at) }}</span>
      </div>

      <!-- 错误信息 -->
      <div v-if="transcription.error_message" class="error-box">
        <strong>错误:</strong> {{ transcription.error_message }}
      </div>

      <!-- 摘要区域 -->
      <div v-if="transcription.summary || editing" class="section summary-section">
        <h3 class="section-title">
          📋 会议摘要
          <button v-if="!editing && transcription.summary && !transcription.approved_at" class="edit-btn" @click="startEdit">✏️ 编辑</button>
          <span v-if="transcription.approved_at" class="approved-badge">✅ 已入库</span>
        </h3>
        <textarea v-if="editing" v-model="editSummary" class="edit-textarea" rows="5"></textarea>
        <div v-else class="section-body">{{ transcription.summary }}</div>
      </div>

      <!-- 关键要点 -->
      <div v-if="(transcription.key_points && transcription.key_points.length > 0) || editing" class="section">
        <h3 class="section-title">🎯 关键要点</h3>
        <textarea v-if="editing" v-model="editKeyPoints" class="edit-textarea" rows="4" placeholder="每行一个要点"></textarea>
        <ul v-else class="key-points">
          <li v-for="(point, i) in transcription.key_points" :key="i">{{ point }}</li>
        </ul>
      </div>

      <!-- 编辑操作栏 -->
      <div v-if="editing" class="edit-actions">
        <button class="action-btn primary" @click="saveEdit">保存修改</button>
        <button class="action-btn" @click="cancelEdit">取消</button>
      </div>

      <!-- 确认入库按钮 / 成功状态 -->
      <div v-if="transcription.summary && !editing" class="approve-section">
        <div v-if="transcription.approved_at || approveSuccess" class="approve-done">
          ✅ 已入库知识库
        </div>
        <button v-else class="action-btn approve" @click="approveToKnowledge" :disabled="approving">
          {{ approving ? '入库中...' : '📥 确认入库知识库' }}
        </button>
      </div>

      <!-- 转写文本 -->
      <div v-if="transcription.transcript" class="section">
        <h3 class="section-title">📝 转写文本</h3>
        <div class="transcript-text">{{ transcription.transcript }}</div>
      </div>

      <!-- 待处理提示 -->
      <div v-if="transcription.status === 'pending' || transcription.status === 'processing'" class="pending-box">
        <div class="spinner"></div>
        <p>正在转写中，请稍候...</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Transcription } from '@/types'
import { meetingApi } from '@/api'

interface Props {
  transcription: Transcription | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  refresh: []
}>()

const summarizing = ref(false)
const editing = ref(false)
const editSummary = ref('')
const editKeyPoints = ref('')
const approving = ref(false)
const approveSuccess = ref(false)

async function generateSummary() {
  if (!props.transcription) return
  summarizing.value = true
  try {
    await meetingApi.summarize(props.transcription.id)
    emit('refresh')
  } catch (e: any) {
    alert(e.response?.data?.detail || '摘要生成失败')
  } finally {
    summarizing.value = false
  }
}

function startEdit() {
  if (!props.transcription) return
  editSummary.value = props.transcription.summary || ''
  const kp = props.transcription.key_points
  editKeyPoints.value = Array.isArray(kp) ? kp.join('\n') : ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  if (!props.transcription) return
  try {
    const keyPoints = editKeyPoints.value.split('\n').map(s => s.trim()).filter(Boolean)
    await meetingApi.updateSummary(props.transcription.id, editSummary.value, keyPoints)
    editing.value = false
    emit('refresh')
  } catch (e: any) {
    alert(e.response?.data?.detail || '保存失败')
  }
}

async function approveToKnowledge() {
  if (!props.transcription) return
  approving.value = true
  try {
    const summary = props.transcription.summary || ''
    const kp = Array.isArray(props.transcription.key_points) ? props.transcription.key_points : []
    await meetingApi.approveToKnowledge(props.transcription.id, summary, kp)
    approveSuccess.value = true
    emit('refresh')
  } catch (e: any) {
    alert(e.response?.data?.detail || '入库失败')
  } finally {
    approving.value = false
  }
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

function formatDuration(seconds: number | null): string {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}分${s}秒`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
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

.section-body {
  font-size: 14px;
  line-height: 1.7;
  color: #a8a29e;
  white-space: pre-wrap;
}

.key-points {
  margin: 0;
  padding-left: 20px;
}

.key-points li {
  font-size: 14px;
  line-height: 1.7;
  color: #a8a29e;
  margin-bottom: 4px;
}

.transcript-text {
  font-size: 14px;
  line-height: 1.8;
  color: #a8a29e;
  white-space: pre-wrap;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
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
