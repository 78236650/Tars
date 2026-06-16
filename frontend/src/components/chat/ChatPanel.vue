<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted } from 'vue'
import { useI18n } from '@/i18n'
import { defineAsyncComponent } from 'vue'
const ChartRenderer = defineAsyncComponent(() => import('@/components/bi/ChartRenderer.vue'))
const StowageViz = defineAsyncComponent(() => import('@/components/wind/StowageViz.vue'))

import PlanCard from './PlanCard.vue'
import TaskCard from './TaskCard.vue'
import RememberMemoryDialog from './RememberMemoryDialog.vue'
import MetricAnswerCard from '@/components/insight/MetricAnswerCard.vue'
import type { InsightMetricAnswer } from '@/api'
import type { ToolCallEvent } from '@/types'
import { renderChatMarkdown } from '@/utils/chatMarkdown'
import { useToast } from '@/composables/useToast'
import BaseIcon from '@/components/common/BaseIcon.vue'

// v2.6: 扩展 message 类型支持 thinking 步骤
interface ThinkingStep {
  id: string
  step: string
  title: string
  detail?: string
  timestamp: string
}
interface ThinkingState {
  isActive: boolean
  steps: ThinkingStep[]
}

interface ChatMessage {
  id: string
  role: string
  content: string
  timestamp: string
  toolCalls?: ToolCallEvent[]
  plan?: any
  planSteps?: any[]
  attachments?: any[]
  thinking?: ThinkingState
  task?: any
  biChart?: any
  insightMetricAnswer?: InsightMetricAnswer
  insightDatasourceId?: string
}

const props = defineProps<{
  messages: ChatMessage[]
  isGenerating?: boolean
  loadingHistory?: boolean
}>()

const emit = defineEmits<{
  quickStart: [text: string]
  citationClick: [payload: { docId: string; title?: string }]
  insightClarify: [payload: { question: string; candidate_metric_keys: string[]; datasourceId: string }]
  stop: []
}>()

const { t } = useI18n()
const toast = useToast()
const quickCards = computed(() => [
  { icon: 'lucide:file-pen-line', label: t('chat.quick.writeCode'), text: t('chat.quick.writeCodePrompt') },
  { icon: 'lucide:bar-chart-3', label: t('chat.quick.dataAnalysis'), text: t('chat.quick.dataAnalysisPrompt') },
  { icon: 'lucide:search', label: t('chat.quick.research'), text: t('chat.quick.researchPrompt') },
  { icon: 'lucide:bug', label: t('chat.quick.debug'), text: t('chat.quick.debugPrompt') },
])

const panelRef = ref<HTMLElement | null>(null)
const collapsedTools = ref<Set<string>>(new Set())
const copiedMessageId = ref<string | null>(null)
const rememberOpen = ref(false)
const rememberUserContent = ref('')
const rememberAssistantContent = ref('')
// v2.6: 处理步骤折叠状态
const expandedThinking = ref<Set<string>>(new Set())

const toggleThinking = (msgId: string) => {
  if (expandedThinking.value.has(msgId)) expandedThinking.value.delete(msgId)
  else expandedThinking.value.add(msgId)
}

const isThinkingExpanded = (msgId: string) => expandedThinking.value.has(msgId)

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const scrollToBottom = async () => {
  await nextTick()
  if (panelRef.value) panelRef.value.scrollTop = panelRef.value.scrollHeight
}

watch(() => props.messages.length, scrollToBottom)
watch(() => props.isGenerating, scrollToBottom)

const isCommandBanner = (m: any) => {
  if (m.role !== 'system') return false
  const c = m.content || ''
  return c.includes('MODE') || c.includes('会话已清空')
}

const getCmdStyle = (content: string) => {
  if (content.includes('PLAN')) return 'bg-amber-900/20 border-amber-700/40 text-amber-300'
  if (content.includes('YOLO')) return 'bg-emerald-900/20 border-emerald-700/40 text-emerald-300'
  if (content.includes('BRAINSTORM')) return 'bg-purple-900/20 border-purple-700/40 text-purple-300'
  if (content.includes('清空')) return 'bg-blue-900/20 border-blue-700/40 text-blue-300'
  return 'bg-slate-800 border-slate-700 text-slate-300'
}

const getCmdIcon = (content: string) => {
  if (content.includes('PLAN')) return 'lucide:circle'
  if (content.includes('YOLO')) return 'lucide:circle'
  if (content.includes('BRAINSTORM')) return 'lucide:lightbulb'
  if (content.includes('清空')) return 'lucide:sparkles'
  return 'lucide:clipboard'
}

const toggleToolCard = (id: string) => {
  if (collapsedTools.value.has(id)) collapsedTools.value.delete(id)
  else collapsedTools.value.add(id)
}

const isStreamingAssistant = (msg: ChatMessage, idx: number) =>
  Boolean(
    props.isGenerating &&
      idx === props.messages.length - 1 &&
      msg.role === 'assistant' &&
      msg.id?.startsWith('streaming-'),
  )

// Hide the global footer once an assistant bubble exists; the message-level
// thinking panel / streamed content already conveys progress. This also covers
// isGenerating getting stuck after done finalizes the streaming message id.
const showGlobalThinking = computed(() => {
  if (!props.isGenerating) return false
  const last = props.messages[props.messages.length - 1]
  return !(last?.role === 'assistant')
})

const formatAssistantContent = (msg: ChatMessage, idx: number) =>
  renderChatMarkdown(msg.content, {
    streaming: isStreamingAssistant(msg, idx),
    copyLabel: t('chat.copy'),
  })

const buildMessageCopyText = (msg: ChatMessage) => {
  const parts: string[] = []

  if (msg.thinking?.steps?.length) {
    const steps = msg.thinking.steps
      .map((step) => `- ${step.title}${step.detail ? `: ${step.detail}` : ''}`)
      .join('\n')
    parts.push(`${t('chat.processingSteps')}\n${steps}`)
  }

  if (msg.toolCalls?.length) {
    for (const tc of msg.toolCalls) {
      if (tc.output?.trim()) parts.push(`[${tc.tool}]\n${tc.output.trim()}`)
      if (tc.error?.trim()) parts.push(`[${tc.tool} error]\n${tc.error.trim()}`)
    }
  }

  if (msg.content?.trim()) parts.push(msg.content.trim())

  if (msg.biChart?.data_summary?.trim()) {
    parts.push(msg.biChart.data_summary.trim())
  }

  return parts.join('\n\n')
}

const canCopyMessage = (msg: ChatMessage) => Boolean(buildMessageCopyText(msg))

const copyMessage = async (msg: ChatMessage) => {
  const text = buildMessageCopyText(msg)
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedMessageId.value = msg.id
    setTimeout(() => {
      if (copiedMessageId.value === msg.id) copiedMessageId.value = null
    }, 2000)
  } catch {}
}

const getPairedUserContent = (assistantIdx: number) => {
  for (let i = assistantIdx - 1; i >= 0; i--) {
    const message = props.messages[i]
    if (message.role === 'user') return message.content || ''
  }
  return ''
}

const openRememberDialog = (msg: ChatMessage, idx: number) => {
  if (msg.role !== 'assistant' || !msg.content?.trim()) return
  rememberUserContent.value = getPairedUserContent(idx)
  rememberAssistantContent.value = msg.content
  rememberOpen.value = true
}

const closeRememberDialog = () => {
  rememberOpen.value = false
}

const onRememberSaved = (count: number, kbCount = 0, promotionTrigger = 'none') => {
  if (kbCount > 0) {
    toast.success(t('chat.remember.savedWithKnowledge', { count, kbCount }))
  } else if (promotionTrigger === 'pending') {
    toast.success(t('chat.remember.savedPendingKb', { count }))
  } else {
    toast.success(t('chat.remember.saved', { count }))
  }
}

onMounted(() => {
  document.addEventListener('click', (e: Event) => {
    const refLink = (e.target as HTMLElement).closest('.knowledge-ref')
    if (refLink) {
      e.preventDefault()
      const docId = refLink.getAttribute('data-doc-id') || ''
      const title = refLink.getAttribute('data-doc-title') || undefined
      if (docId) emit('citationClick', { docId, title })
      return
    }

    const btn = (e.target as HTMLElement).closest('.code-block-copy')
    if (!btn) return
    const block = btn.closest('.code-block')
    if (!block) return
    const code = block.querySelector('code')
    if (!code) return
    navigator.clipboard.writeText(code.textContent || '').then(() => {
      ;(btn as HTMLElement).textContent = '✓'
      setTimeout(() => { (btn as HTMLElement).textContent = t('chat.copy') }, 2000)
    }).catch(() => {})
  })
})
</script>

<template>
  <div ref="panelRef" class="flex-1 overflow-y-auto scroll-smooth">
    <div v-if="messages.length === 0 && loadingHistory" class="flex flex-col items-center justify-center h-full px-6 py-12">
      <div class="w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full animate-spin mb-3"></div>
      <p class="text-sm text-slate-400">{{ t('chat.restoringHistory') }}</p>
    </div>

    <div v-else-if="messages.length === 0" class="flex flex-col items-center justify-center h-full px-6">
      <div class="w-16 h-16 bg-gradient-to-br from-blue-500/20 to-purple-600/20 rounded-2xl flex items-center justify-center mb-4 ring-1 ring-blue-500/20">
        <BaseIcon icon="lucide:message-circle" :size="32" class="text-blue-400" />
      </div>
      <h2 class="text-xl font-semibold text-white mb-1">PortMeta Agent</h2>
      <p class="text-xs text-slate-500 mb-2">Miluo Lab 出品</p>
      <p class="text-sm text-slate-400 mb-8">{{ t('chat.workspaceSubtitle') }}</p>

      <!-- 快捷入口 -->
      <div class="grid grid-cols-2 gap-3 w-full max-w-md">
        <button
          v-for="card in quickCards"
          :key="card.text"
          @click="$emit('quickStart', card.text)"
          class="flex items-center gap-3 px-4 py-3 bg-slate-800/60 border border-slate-700/60 rounded-xl hover:border-blue-500/50 hover:bg-slate-800 transition-all text-left group"
        >
          <BaseIcon :icon="card.icon" :size="20" class="group-hover:scale-110 transition-transform" />
          <div>
            <p class="text-sm text-slate-300 group-hover:text-white transition-colors">{{ card.label }}</p>
            <p class="text-xs text-slate-500">{{ card.text }}</p>
          </div>
        </button>
      </div>
    </div>

    <div v-else class="max-w-3xl mx-auto px-6 py-6 space-y-1">
      <template v-for="(msg, idx) in messages" :key="idx">

        <div v-if="isCommandBanner(msg)" class="flex justify-center py-2">
          <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-medium" :class="getCmdStyle(msg.content)">
            <BaseIcon :icon="getCmdIcon(msg.content)" :size="14" />
            <span>{{ msg.content }}</span>
          </div>
        </div>

        <PlanCard v-else-if="(msg as any).planSteps" :plan="(msg as any).plan" :steps="(msg as any).planSteps" />

        <div v-else class="flex gap-3 py-2" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
          <div class="flex-shrink-0 mt-1">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
              :class="{
                'bg-blue-600 text-white': msg.role === 'user',
                'bg-gradient-to-br from-blue-500 to-purple-600 text-white': msg.role === 'assistant',
                'bg-red-900/50 text-red-300': msg.role === 'system',
              }">
              <template v-if="msg.role === 'user'">{{ t('chat.role.user') }}</template>
              <template v-else-if="msg.role === 'assistant'">T</template>
              <template v-else>!</template>
            </div>
          </div>

          <div class="flex-1 min-w-0" :class="msg.role === 'user' ? 'flex flex-col items-end' : ''">
            <div class="flex items-center gap-2 mb-1" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
              <span class="text-xs font-semibold" :class="{
                'text-blue-400': msg.role === 'user',
                'text-purple-400': msg.role === 'assistant',
                'text-red-400': msg.role === 'system',
              }">{{ msg.role === 'user' ? t('chat.role.userEn') : msg.role === 'assistant' ? t('chat.role.assistant') : t('chat.role.systemEn') }}</span>
              <span class="text-[10px] text-slate-600">{{ formatTime(msg.timestamp) }}</span>
            </div>

            <!-- 用户气泡 -->
            <div v-if="msg.role === 'user'" class="inline-block max-w-[85%] px-4 py-2.5 bg-blue-600 text-white rounded-2xl rounded-tr-sm">
              <div class="whitespace-pre-wrap text-sm leading-relaxed">{{ msg.content }}</div>
              <div v-if="msg.attachments?.length" class="mt-2 flex flex-wrap gap-1.5">
                <span v-for="att in msg.attachments" :key="att.file_id" class="text-xs px-2 py-0.5 bg-blue-500/50 rounded-full">{{ att.name }}</span>
              </div>
            </div>

            <!-- 任务卡片 -->
            <TaskCard v-if="msg.role === 'task' && msg.task" :task="msg.task" class="max-w-[95%]" />

            <!-- TARS 卡片：处理步骤 → 工具调用 → 正文（与流式事件顺序一致） -->
            <div v-else-if="msg.role === 'assistant' || msg.role === 'system'" class="max-w-[95%]">
              <!-- v2.6.1: 处理步骤面板 — 活跃时强制展开，置于正文上方 -->
              <div v-if="msg.thinking && msg.thinking.steps.length > 0" class="mb-3">
                <div
                  class="thinking-panel"
                  :class="{ 'cursor-pointer': !msg.thinking.isActive }"
                  @click="msg.thinking.isActive ? null : toggleThinking(msg.id)"
                >
                  <div class="thinking-header">
                    <BaseIcon :icon="msg.thinking.isActive || isThinkingExpanded(msg.id) ? 'lucide:chevron-down' : 'lucide:chevron-right'" :size="12" />
                    <BaseIcon
                      :icon="msg.thinking.isActive ? 'lucide:loader-circle' : 'lucide:list-checks'"
                      :size="14"
                      :class="{ 'animate-spin': msg.thinking.isActive }"
                    />
                    <span>{{ msg.thinking.isActive ? t('chat.processing') : t('chat.processingSteps') }}</span>
                    <span class="step-count">({{ msg.thinking.steps.length }})</span>
                  </div>

                  <div v-if="msg.thinking.isActive || isThinkingExpanded(msg.id)" class="thinking-steps">
                    <div
                      v-for="step in msg.thinking.steps"
                      :key="step.id"
                      class="step-item"
                    >
                      <span class="step-icon">{{ step.step }}</span>
                      <div class="step-text">
                        <span class="step-title">{{ step.title }}</span>
                        <span v-if="step.detail" class="step-detail">{{ step.detail }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 工具调用 -->
              <div v-if="msg.toolCalls?.length" class="mb-3 space-y-1.5">
                <div v-for="tc in msg.toolCalls" :key="tc.id || tc.tool" class="bg-stone-800/70 border border-amber-100/10 rounded-lg overflow-hidden">
                  <button @click="toggleToolCard(tc.id || tc.tool)" class="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-stone-700/60 transition-colors">
                    <BaseIcon icon="lucide:chevron-right" :size="12" class="transition-transform" :class="collapsedTools.has(tc.id || tc.tool) ? '' : 'rotate-90'" />
                    <BaseIcon icon="lucide:wrench" :size="14" class="text-amber-400" />
                    <span class="font-medium">{{ tc.tool }}</span>
                    <span v-if="tc.duration" class="text-stone-600 ml-auto">{{ tc.duration }}s</span>
                    <BaseIcon v-if="tc.output && !tc.error" icon="lucide:check" :size="14" class="text-amber-500 ml-1" />
                    <BaseIcon v-if="tc.error" icon="lucide:x" :size="14" class="text-red-500 ml-1" />
                  </button>
                  <div v-if="!collapsedTools.has(tc.id || tc.tool)" class="px-3 pb-2">
                    <div v-if="tc.output" class="text-xs text-stone-400 bg-stone-950/50 rounded p-2 max-h-32 overflow-auto font-mono whitespace-pre-wrap">{{ tc.output }}</div>
                    <div v-if="tc.error" class="text-xs text-red-400 bg-red-950/30 rounded p-2">{{ tc.error }}</div>
                     <!-- BI 工具结果中的图表 -->
                    <div v-if="tc.metadata?.chart" class="mt-2">
                      <ChartRenderer
                        :chart-type="tc.metadata.chart.chart_type"
                        :echarts-option="tc.metadata.chart.echarts_option"
                        :title="tc.metadata.chart.title"
                      />
                    </div>
                     <!-- 风电配载可视化 -->
                     <div v-if="tc.metadata?.placements" class="mt-2">
                       <StowageViz :result="tc.metadata" />
                     </div>
                     <!-- 图像生成结果 -->
                     <div v-if="tc.metadata?.image_base64 || tc.metadata?.image_url" class="mt-2">
                       <img
                         :src="tc.metadata.image_base64 || tc.metadata.image_url"
                         :alt="tc.tool + ' 生成结果'"
                         class="max-w-full rounded-lg border border-amber-100/10"
                         style="max-height:512px"
                       />
                       <div v-if="tc.metadata.image_url" class="mt-1 text-xs text-stone-500">
                         <a :href="tc.metadata.image_url" target="_blank" class="text-amber-400 underline">查看原图</a>
                       </div>
                     </div>
                     <!-- 视频生成结果 -->
                     <div v-if="tc.metadata?.video_url" class="mt-2">
                       <video
                         :src="tc.metadata.video_url"
                         controls
                         class="max-w-full rounded-lg border border-amber-100/10"
                         style="max-height:480px"
                       />
                       <div class="mt-1 text-xs text-stone-500">
                         <a :href="tc.metadata.video_url" target="_blank" class="text-amber-400 underline">查看视频</a>
                       </div>
                     </div>
                     <!-- 视频生成中 -->
                     <div v-if="tc.metadata?.status === 'processing'" class="mt-2 p-3 rounded-lg border border-amber-400/30 bg-amber-500/5">
                       <div class="flex items-center gap-2 mb-2">
                         <span class="w-3 h-3 bg-amber-400 rounded-full animate-pulse"></span>
                         <span class="text-sm text-amber-300 font-medium">🎬 视频生成中</span>
                       </div>
                       <div class="text-xs text-stone-400 space-y-1">
                         <div>任务 ID: <code class="text-amber-400/80">{{ tc.metadata.task_id }}</code></div>
                         <div v-if="tc.metadata.prompt">描述: {{ tc.metadata.prompt }}</div>
                         <div class="mt-1">预计 3-10 分钟，完成后 Agent 可查询: <code class="text-amber-400/60">GET /api/generation/video/{{ tc.metadata.task_id }}</code></div>
                       </div>
                     </div>
                   </div>
                </div>
              </div>

              <div
                v-if="msg.content"
                class="markdown-body text-sm text-slate-300 leading-relaxed"
                :class="{ 'markdown-body--streaming': isStreamingAssistant(msg, idx) }"
                v-html="formatAssistantContent(msg, idx)"
              />

              <div v-if="msg.insightMetricAnswer && msg.insightDatasourceId" class="mt-3">
                <MetricAnswerCard
                  :answer="msg.insightMetricAnswer"
                  :datasource-id="msg.insightDatasourceId"
                  @clarify="(p) => emit('insightClarify', { ...p, datasourceId: msg.insightDatasourceId! })"
                />
              </div>

              <!-- BI 图表渲染 -->
              <div v-if="msg.biChart" class="mt-3">
                <div class="text-xs text-stone-500 mb-2 flex items-center gap-1">
                  <BaseIcon icon="lucide:bar-chart-3" :size="14" />
                  <span>{{ msg.biChart.title || t('chat.chartFallback') }}</span>
                </div>
                <ChartRenderer
                  :chart-type="msg.biChart.chart_type"
                  :echarts-option="msg.biChart.echarts_option"
                  :title="msg.biChart.title"
                />
                <div v-if="msg.biChart.data_summary" class="text-xs text-stone-500 mt-2">{{ msg.biChart.data_summary }}</div>
              </div>

              <div v-if="msg.role === 'assistant' && canCopyMessage(msg)" class="mt-2 flex items-center gap-1">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 transition-colors hover:bg-white/[0.04] hover:text-slate-300"
                  :title="t('chat.copy')"
                  @click="copyMessage(msg)"
                >
                  <BaseIcon :icon="copiedMessageId === msg.id ? 'lucide:check' : 'lucide:clipboard'" :size="14" />
                  <span>{{ copiedMessageId === msg.id ? t('chat.copied') : t('chat.copy') }}</span>
                </button>
                <button
                  v-if="msg.content?.trim() && !isStreamingAssistant(msg, idx)"
                  type="button"
                  class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 transition-colors hover:bg-white/[0.04] hover:text-amber-300"
                  :title="t('chat.remember')"
                  @click="openRememberDialog(msg, idx)"
                >
                  <BaseIcon icon="lucide:brain" :size="14" />
                  <span>{{ t('chat.remember') }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 思考中：仅在尚无 assistant 气泡时显示（避免与消息内 thinking 面板重复） -->
      <div v-if="showGlobalThinking" class="flex items-center justify-between gap-3 pl-11 py-2 pr-2">
        <div class="flex items-center gap-3">
          <div class="flex gap-1">
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0s"></span>
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.2s"></span>
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.4s"></span>
          </div>
          <span class="text-xs text-slate-500">{{ t('chat.thinking') }}</span>
        </div>
        <button
          type="button"
          data-test="chat-stop-inline"
          class="shrink-0 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-200 transition hover:bg-rose-500/20"
          :title="t('chat.stopTitle')"
          @click="emit('stop')"
        >
          {{ t('chat.stop') }}
        </button>
      </div>

      <!-- 流式回复中：assistant 气泡已出现时，在消息区也提供停止入口 -->
      <div
        v-else-if="isGenerating"
        class="sticky bottom-0 z-10 flex justify-end px-2 py-2"
      >
        <button
          type="button"
          data-test="chat-stop-inline"
          class="rounded-lg border border-rose-500/40 bg-rose-950/90 px-3 py-1.5 text-xs font-medium text-rose-200 shadow-lg backdrop-blur transition hover:bg-rose-500/20"
          :title="t('chat.stopTitle')"
          @click="emit('stop')"
        >
          <BaseIcon icon="lucide:square" :size="16" class="text-rose-200" />
          {{ t('chat.stop') }}
        </button>
      </div>
    </div>

    <RememberMemoryDialog
      :open="rememberOpen"
      :user-content="rememberUserContent"
      :assistant-content="rememberAssistantContent"
      @close="closeRememberDialog"
      @saved="onRememberSaved"
    />
  </div>
</template>
<style>
@import "highlight.js/styles/atom-one-dark.css";
.code-block { position: relative; margin: 1rem 0; border-radius: 0.75rem; overflow: hidden; border: 1px solid rgba(245,158,11,0.15); background: rgba(8,7,5,0.95); }
.code-block-header { display: flex; align-items: center; justify-content: space-between; padding: 0.375rem 1rem; background: rgba(20,17,15,0.9); font-size: 0.75rem; border-bottom: 1px solid rgba(245,158,11,0.12); }
.code-block-lang { color: #78716c; text-transform: lowercase; }
.code-block-copy { color: #a8a29e; cursor: pointer; background: none; border: none; font-size: 0.75rem; }
.code-block-copy:hover { color: #e7e5e4; }
.code-block-pre { margin: 0; border-radius: 0; overflow-x: auto; background: rgba(8,7,5,0.95); }
.code-block pre { margin: 0; border-radius: 0; overflow-x: auto; }
.code-block code,
.code-block pre code { display: block; padding: 1rem 1.125rem; font-size: 0.8125rem; line-height: 1.6; color: #e7e5e4 !important; white-space: pre; word-break: normal; overflow-wrap: normal; }
.code-block .hljs { color: #e7e5e4; }
.markdown-body > :first-child { margin-top: 0; }
.markdown-body--streaming { opacity: 0.95; }
.markdown-body h1 { font-size: 1.25rem; font-weight: 700; color: #fff; margin: 1.5rem 0 0.75rem; }
.markdown-body h1:first-child { margin-top: 0; }
.markdown-body h2 { font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin: 1.25rem 0 0.5rem; }
.markdown-body h3 { font-size: 1rem; font-weight: 500; color: #e2e8f0; margin: 1rem 0 0.5rem; }
.markdown-body p { margin-bottom: 0.75rem; line-height: 1.65; }
.markdown-body ul { list-style: disc; padding-left: 1.5rem; margin-bottom: 0.75rem; }
.markdown-body ol { list-style: decimal; padding-left: 1.5rem; margin-bottom: 0.75rem; }
.markdown-body li { margin-bottom: 0.25rem; }
.markdown-body a { color: #fbbf24; text-decoration: underline; }
.markdown-body strong { color: #f1f5f9; font-weight: 600; }
.markdown-body code { background: rgba(20,17,15,0.9); color: #fbbf24; font-size: 0.8rem; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-family: "SF Mono","Fira Code",monospace; border: 1px solid rgba(245,158,11,0.15); word-break: break-word; }
.markdown-body pre { background: rgba(8,7,5,0.8); border: 1px solid rgba(245,158,11,0.15); border-radius: 0.75rem; padding: 0; margin: 1rem 0; overflow-x: auto; }
.markdown-body pre code { background: transparent; color: #d6d3d1; padding: 0; font-size: 0.8rem; line-height: 1.5; border: none; }
.markdown-body .table-wrap { overflow-x: auto; margin: 0.75rem 0; }
.markdown-body table { width: 100%; font-size: 0.75rem; border-collapse: collapse; margin: 0; }
.markdown-body th { background: rgba(20,17,15,0.9); color: #e7e5e4; padding: 0.5rem 0.75rem; text-align: left; font-weight: 500; border: 1px solid rgba(245,158,11,0.15); }
.markdown-body td { padding: 0.5rem 0.75rem; border: 1px solid rgba(245,158,11,0.1); color: #a8a29e; }
.markdown-body blockquote { border-left: 3px solid rgba(217,119,6,0.4); padding-left: 1rem; margin: 0.75rem 0; color: #a8a29e; font-style: italic; }
.markdown-body hr { border-color: rgba(245,158,11,0.15); margin: 1rem 0; }
.markdown-body img { border-radius: 0.5rem; max-width: 100%; margin: 0.75rem 0; }
/* highlight.js overrides for dark theme */
.hljs { background: transparent !important; color: #e7e5e4; }
.code-block .hljs-keyword { color: #c4b5fd; }
.code-block .hljs-string { color: #86efac; }
.code-block .hljs-number { color: #fcd34d; }
.code-block .hljs-built_in,
.code-block .hljs-title { color: #7dd3fc; }
.code-block .hljs-comment { color: #78716c; }

/* v2.6: 处理步骤面板 */
.thinking-panel {
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(217,119,6,0.06);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #78716c;
  user-select: none;
}

.thinking-header:hover {
  color: #a8a29e;
}

.step-count {
  opacity: 0.7;
}

.thinking-steps {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(245,158,11,0.15);
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  border-left: 2px solid rgba(245,158,11,0.2);
  margin-left: 4px;
  padding-left: 12px;
}

.step-item:first-child {
  margin-top: 4px;
}

.step-icon {
  font-size: 14px;
  margin-top: 1px;
  flex-shrink: 0;
}

.step-text {
  flex: 1;
  min-width: 0;
}

.step-title {
  color: #a8a29e;
  display: block;
}

.step-detail {
  color: #78716c;
  font-size: 11px;
  display: block;
  margin-top: 2px;
  word-break: break-all;
  max-height: 60px;
  overflow: hidden;
}

:deep(.knowledge-ref) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0 2px;
  padding: 1px 8px;
  border-radius: 9999px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(96, 165, 250, 0.25);
  color: #93c5fd;
  font-size: 12px;
  text-decoration: none;
  vertical-align: baseline;
}

:deep(.knowledge-ref:hover) {
  background: rgba(59, 130, 246, 0.25);
  color: #bfdbfe;
}
</style>
