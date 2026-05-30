<script setup lang="ts">
import { computed, ref, onMounted, onActivated, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useChatStore } from '@/stores/chat'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import WorkflowStrip from '@/components/insight/WorkflowStrip.vue'
import { biApi, insightApi } from '@/api'
import type { InsightMetricAnswer } from '@/api'
import { getErrorDetail } from '@/utils/errorExtractor'
import BaseIcon from '@/components/common/BaseIcon.vue'
import ActiveSkillsBar from '@/components/chat/ActiveSkillsBar.vue'
import KnowledgeCitationPanel from '@/components/chat/KnowledgeCitationPanel.vue'
import QueueStatus from '@/components/chat/QueueStatus.vue'
import WarningBanner from '@/components/chat/WarningBanner.vue'
import ApprovalDialog from '@/components/chat/ApprovalDialog.vue'
import PlanReviewDialog from '@/components/chat/PlanReviewDialog.vue'
import HandoffDialog from '@/components/chat/HandoffDialog.vue'

defineOptions({ name: 'ChatView' })

const settingsStore = useSettingsStore()
const chatStore = useChatStore()
const reminderNotificationsStore = useReminderNotificationsStore()
const wsStore = useWsStore()
const { t } = useI18n()
const toast = useToast()
const route = useRoute()

const messages = computed(() => chatStore.currentMessages)
const activeSkills = computed(() => chatStore.currentActiveSkills)
const messagesLoading = computed(() => chatStore.messagesLoading)
const externalNotificationCount = computed(
  () => chatStore.externalApprovalCount + chatStore.externalHandoffCount,
)

const inputMessage = ref('')
const insightMetricQaEnabled = ref(false)
const insightDatasourceId = ref('')
const insightDatasources = ref<{ id: string; name: string }[]>([])
const insightAsking = ref(false)
const insightAskAbort = ref<AbortController | null>(null)
const insightWorkflowEnabled = ref(false)
const INSIGHT_ASK_RE = /^\/(问数|metric)\s+(.+)/is
const INSIGHT_DS_STORAGE = 'tars_insight_ask_datasource_id'
const inputRef = ref<HTMLTextAreaElement | null>(null)
const citationOpen = ref(false)
const citationDocId = ref('')
const citationTitleHint = ref('')

const autoResize = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

const showCommands = ref(false)
const commands = computed(() => [
  { name: '/plan', desc: t('chat.command.plan'), usage: '/plan ' },
  { name: '/yolo', desc: t('chat.command.yolo'), usage: '/yolo' },
  { name: '/brainstorm', desc: t('chat.command.brainstorm'), usage: '/brainstorm ' },
  { name: '/subagent', desc: t('chat.command.subagent'), usage: '/subagent code ' },
  { name: '/skill', desc: t('chat.command.skill'), usage: '/skill ' },
  { name: '/clear', desc: t('chat.command.clear'), usage: '/clear' },
  { name: '/help', desc: t('chat.command.help'), usage: '/help' },
])
const selectCommand = (cmd: (typeof commands.value)[number]) => {
  inputMessage.value = cmd.usage
  showCommands.value = false
}
const toggleCommands = () => {
  showCommands.value = !showCommands.value
}

const attachments = ref<{ file_id: string; name: string; type: string; mime_type: string; size: number; preview: string }[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const MAX_FILES = 5
const MAX_SIZE = 50 * 1024 * 1024

const handleFileSelect = () => {
  fileInputRef.value?.click()
}

const onFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return

  for (const file of Array.from(files)) {
    if (attachments.value.length >= MAX_FILES) {
      toast.error(t('chat.maxFiles'))
      break
    }
    if (file.size > MAX_SIZE) {
      toast.error(t('chat.fileTooLarge'))
      continue
    }
    await uploadFile(file)
  }
  input.value = ''
}

const uploadFile = async (file: File) => {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const resp = await fetch('/api/files/upload', { method: 'POST', body: formData })
    if (resp.ok) {
      const data = await resp.json()
      attachments.value.push(data.file)
    } else {
      const err = await resp.json()
      toast.error(err.detail || t('chat.uploadFailed'))
    }
  } catch {
    toast.error(t('chat.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

const removeAttachment = (index: number) => {
  attachments.value.splice(index, 1)
}

const quickStart = (text: string) => {
  inputMessage.value = text
}

const runInsightAsk = async (
  question: string,
  candidateKeys?: string[],
  userEcho?: string
) => {
  const sessionId = chatStore.currentSessionId
  const dsId = insightDatasourceId.value || (route.query.datasource_id as string) || ''
  if (!sessionId || !dsId) {
    toast.error(t('insight.metric.needDatasource'))
    return
  }
  if (userEcho) {
    chatStore.appendUserMessage(sessionId, {
      id: `${Date.now()}-u`,
      role: 'user',
      content: userEcho,
      timestamp: new Date().toISOString(),
    })
  }
  insightAsking.value = true
  insightAskAbort.value?.abort()
  const controller = new AbortController()
  insightAskAbort.value = controller
  try {
    const answer: InsightMetricAnswer = await insightApi.ask(dsId, {
      question,
      candidate_metric_keys: candidateKeys,
      session_id: sessionId,
    }, { signal: controller.signal })
    chatStore.appendMessage(sessionId, {
      id: `${Date.now()}-insight`,
      role: 'assistant',
      content: answer.branch === 'hit_partial' ? t('insight.metric.partialHint') : t('insight.metric.answerReady'),
      timestamp: new Date().toISOString(),
      insightMetricAnswer: answer,
      insightDatasourceId: dsId,
    })
  } catch (e: unknown) {
    if (controller.signal.aborted) {
      toast.info(t('chat.generationStopped'))
    } else {
      toast.error(getErrorDetail(e, t('insight.metric.askFailed')))
    }
  } finally {
    insightAsking.value = false
    if (insightAskAbort.value === controller) {
      insightAskAbort.value = null
    }
  }
}

const isGenerating = computed(() => wsStore.isGenerating || insightAsking.value)

const stopGeneration = () => {
  const sessionId = chatStore.currentSessionId
  if (insightAsking.value) {
    insightAskAbort.value?.abort()
    insightAsking.value = false
    return
  }
  if (!sessionId || !wsStore.isGenerating) return
  wsStore.stopGeneration(sessionId)
}

const sendMessage = async () => {
  if ((!inputMessage.value.trim() && attachments.value.length === 0) || !wsStore.isConnected) return
  if (!chatStore.currentSessionId) return

  const sessionId = chatStore.currentSessionId
  chatStore.clearActiveSkills(sessionId)

  const messageContent = inputMessage.value

  const metricMatch = messageContent.trim().match(INSIGHT_ASK_RE)
  if (metricMatch && insightMetricQaEnabled.value) {
    const question = metricMatch[2].trim()
    inputMessage.value = ''
    attachments.value = []
    await runInsightAsk(question, undefined, messageContent.trim())
    return
  }
  const isFirstMessage = messages.value.length === 0

  chatStore.appendUserMessage(sessionId, {
    id: Date.now().toString(),
    role: 'user',
    content: messageContent,
    timestamp: new Date().toISOString(),
    attachments: attachments.value.length > 0 ? [...attachments.value] : undefined,
  })

  wsStore.isGenerating = true

  const payload: any = {
    session_id: sessionId,
    content: messageContent,
  }
  if (attachments.value.length > 0) {
    payload.file_ids = attachments.value.map(a => a.file_id)
  }

  wsStore.send(payload)

  inputMessage.value = ''
  attachments.value = []
  if (inputRef.value) inputRef.value.style.height = 'auto'

  if (isFirstMessage && messageContent.trim()) {
    const newTitle = messageContent.trim().slice(0, 30)
    try {
      await chatStore.updateTitle(sessionId, newTitle)
    } catch (e) {
      console.error('更新标题失败', e)
    }
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  const ctrl = e.ctrlKey || e.metaKey
  if (ctrl && (e.key === '/' || e.key === 'k')) { e.preventDefault(); toggleCommands() }
  if (ctrl && e.key === 'l') { e.preventDefault(); inputMessage.value = '/clear'; sendMessage() }
}

const handleInputKeydown = (e: KeyboardEvent) => {
  const mod = e.ctrlKey || e.metaKey
  if (mod && e.key === 'Enter') {
    e.preventDefault()
    sendMessage()
  }
}

onMounted(async () => {
  chatStore.initChatRealtime()
  await chatStore.initIfEmpty()
  try {
    const ver = await insightApi.version()
    const phase = (ver.phase as Record<string, unknown>) || {}
    insightMetricQaEnabled.value = Boolean(phase.metric_qa_in_chat)
    insightWorkflowEnabled.value = Boolean(phase.workflow)
  } catch {
    insightMetricQaEnabled.value = false
  }
  try {
    const res = await biApi.listDataSources()
    insightDatasources.value = (res.datasources || []).map((d) => ({ id: d.id, name: d.name }))
    const stored = localStorage.getItem(INSIGHT_DS_STORAGE)
    const fromRoute = typeof route.query.datasource_id === 'string' ? route.query.datasource_id : ''
    insightDatasourceId.value = fromRoute || stored || insightDatasources.value[0]?.id || ''
  } catch {
    insightDatasources.value = []
  }
  if (chatStore.currentSessionId) {
    await chatStore.loadSessionMessages(chatStore.currentSessionId)
  }
  const prompt = route.query.prompt
  if (typeof prompt === 'string' && prompt.trim()) {
    inputMessage.value = prompt.trim()
    autoResize()
  }
  try {
    await reminderNotificationsStore.loadList()
  } catch {}
  document.addEventListener('keydown', handleKeydown)
})

watch(() => chatStore.currentSessionId, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await chatStore.loadSessionMessages(newId)
  }
})

onActivated(async () => {
  const sessionId = chatStore.currentSessionId
  if (sessionId && !wsStore.isGenerating) {
    await chatStore.loadSessionMessages(sessionId)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

const openCitation = (payload: { docId: string; title?: string }) => {
  citationDocId.value = payload.docId
  citationTitleHint.value = payload.title || ''
  citationOpen.value = true
}

const closeCitation = () => {
  citationOpen.value = false
  citationDocId.value = ''
  citationTitleHint.value = ''
}

watch(insightDatasourceId, (id) => {
  if (id) localStorage.setItem(INSIGHT_DS_STORAGE, id)
})

const onInsightClarify = async (payload: {
  question: string
  candidate_metric_keys: string[]
  datasourceId: string
}) => {
  insightDatasourceId.value = payload.datasourceId
  await runInsightAsk(payload.question, payload.candidate_metric_keys)
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] bg-surface-1/55">
      <header class="flex shrink-0 items-center gap-2.5 border-b border-amber-100/10 px-4 py-2">
        <div class="flex min-w-0 items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-stone-500">
          <span class="shrink-0">{{ t('chat.conversation') }}</span>
          <span class="h-1 w-1 shrink-0 rounded-full bg-slate-600"></span>
          <span class="truncate">{{ chatStore.currentSessionId ? t('chat.liveSession') : t('chat.idleSession') }}</span>
        </div>
        <span class="h-3 w-px shrink-0 bg-amber-100/10" aria-hidden="true"></span>
        <div class="flex shrink-0 items-center gap-1.5">
          <span class="h-2 w-2 rounded-full" :class="wsStore.isConnected ? 'bg-emerald-400' : 'bg-rose-400'"></span>
          <span class="text-xs text-stone-400">{{ wsStore.isConnected ? t('chat.connected') : t('chat.disconnected') }}</span>
        </div>
        <span
          class="ml-auto max-w-[min(240px,40%)] truncate rounded-full border border-amber-100/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-stone-300"
          :title="settingsStore.currentModel || t('chat.notSelectedModel')"
        >
          {{ settingsStore.currentModel || t('chat.notSelectedModel') }}
        </span>
      </header>

      <ActiveSkillsBar :skills="activeSkills" />

      <WorkflowStrip
        v-if="insightWorkflowEnabled && insightDatasourceId"
        :datasource-id="insightDatasourceId"
        :session-id="chatStore.currentSessionId || undefined"
        :datasources="insightDatasources"
        @update:datasource-id="(id) => (insightDatasourceId = id)"
        @forged="() => {}"
      />

      <ChatPanel
        :messages="messages"
        :is-generating="isGenerating"
        :loading-history="messagesLoading"
        @quick-start="quickStart"
        @citation-click="openCitation"
        @insight-clarify="onInsightClarify"
        @stop="stopGeneration"
      />

      <KnowledgeCitationPanel
        :open="citationOpen"
        :doc-id="citationDocId"
        :title-hint="citationTitleHint"
        @close="closeCitation"
      />

      <QueueStatus />
      <p
        v-if="externalNotificationCount > 0"
        class="mx-4 mb-2 rounded-lg border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
      >
        {{ t('chat.externalNotifications', { count: externalNotificationCount }) }}
      </p>
      <WarningBanner />
      <ApprovalDialog />
      <PlanReviewDialog />
      <HandoffDialog />

      <footer class="border-t border-amber-100/10 px-6 py-4">
        <div
          v-if="insightMetricQaEnabled && insightDatasources.length"
          class="mb-3 flex flex-wrap items-center gap-2 text-xs text-stone-400"
        >
          <span>{{ t('insight.metric.askDatasource') }}</span>
          <select
            v-model="insightDatasourceId"
            class="rounded-lg border border-amber-100/10 bg-white/[0.04] px-2 py-1 text-stone-200"
          >
            <option v-for="ds in insightDatasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
          </select>
          <span class="text-stone-500">{{ t('insight.metric.askHint') }}</span>
        </div>
        <div v-if="attachments.length > 0" class="mb-3 flex flex-wrap gap-2">
          <div
            v-for="(att, idx) in attachments"
            :key="att.file_id"
            class="flex items-center gap-2 rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-sm"
          >
            <BaseIcon v-if="att.type === 'image'" icon="lucide:image" :size="14" />
            <BaseIcon v-else icon="lucide:file" :size="14" />
            <span class="max-w-[120px] truncate text-stone-300">{{ att.name }}</span>
            <button @click="removeAttachment(idx)" class="text-stone-500 transition hover:text-red-400"><BaseIcon icon="lucide:x" :size="14" /></button>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            @click="handleFileSelect"
            :disabled="uploading || attachments.length >= MAX_FILES"
            class="rounded-xl p-3 transition hover:bg-amber-500/10 disabled:opacity-50"
            :title="t('chat.uploadTooltip')"
          >
            <BaseIcon icon="lucide:paperclip" :size="20" class="text-stone-400" />
          </button>

          <div class="relative">
            <button
              @click="toggleCommands"
              class="rounded-xl p-3 transition hover:bg-amber-500/10"
              :title="t('chat.commandButton')"
            >
              <BaseIcon icon="lucide:zap" :size="20" class="text-stone-400" />
            </button>
            <div
              v-if="showCommands"
              class="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-2xl border border-amber-100/10 bg-surface-1 p-2 shadow-xl"
            >
              <p class="px-3 py-2 text-xs uppercase tracking-[0.16em] text-stone-500">{{ t('chat.commandTitle') }}</p>
              <button
                v-for="cmd in commands"
                :key="cmd.name"
                class="flex w-full flex-col rounded-xl px-3 py-2 text-left transition hover:bg-amber-500/10"
                @click="selectCommand(cmd)"
              >
                <span class="text-sm font-medium text-stone-100">{{ cmd.name }}</span>
                <span class="text-xs text-stone-400">{{ cmd.desc }}</span>
              </button>
            </div>
          </div>

          <input ref="fileInputRef" type="file" multiple class="hidden" @change="onFileChange" />

          <textarea
            ref="inputRef"
            v-model="inputMessage"
            rows="1"
            :placeholder="t('chat.placeholder')"
            class="max-h-40 min-h-[48px] flex-1 resize-none rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 text-sm text-stone-100 outline-none transition placeholder:text-stone-500 focus:border-amber-300/25"
            @input="autoResize"
            @keydown="handleInputKeydown"
          />

          <button
            v-if="isGenerating"
            type="button"
            data-test="chat-stop-button"
            @click="stopGeneration"
            class="rounded-2xl border border-rose-500/50 bg-rose-500/15 px-5 py-3 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/25"
            :title="t('chat.stopTitle')"
          >
            <BaseIcon icon="lucide:square" :size="16" /> {{ t('chat.stop') }}
          </button>
          <button
            @click="sendMessage"
            :disabled="isGenerating || !wsStore.isConnected || (!inputMessage.trim() && attachments.length === 0)"
            class="rounded-2xl bg-amber-500 px-5 py-3 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-stone-700 disabled:text-stone-400"
          >
            {{ t('common.send') }}
          </button>
        </div>
      </footer>
  </div>
</template>
