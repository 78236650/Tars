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
import ActiveSkillsBar from '@/components/chat/ActiveSkillsBar.vue'
import KnowledgeCitationPanel from '@/components/chat/KnowledgeCitationPanel.vue'
import QueueStatus from '@/components/chat/QueueStatus.vue'
import WarningBanner from '@/components/chat/WarningBanner.vue'

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

const inputMessage = ref('')
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

const sendMessage = async () => {
  if ((!inputMessage.value.trim() && attachments.value.length === 0) || !wsStore.isConnected) return
  if (!chatStore.currentSessionId) return

  const sessionId = chatStore.currentSessionId
  chatStore.clearActiveSkills(sessionId)

  const messageContent = inputMessage.value
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
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] bg-[#14110f]/55">
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

      <ChatPanel
        :messages="messages"
        :is-generating="wsStore.isGenerating"
        :loading-history="messagesLoading"
        @quick-start="quickStart"
        @citation-click="openCitation"
      />

      <KnowledgeCitationPanel
        :open="citationOpen"
        :doc-id="citationDocId"
        :title-hint="citationTitleHint"
        @close="closeCitation"
      />

      <QueueStatus />
      <WarningBanner />

      <footer class="border-t border-amber-100/10 px-6 py-4">
        <div v-if="attachments.length > 0" class="mb-3 flex flex-wrap gap-2">
          <div
            v-for="(att, idx) in attachments"
            :key="att.file_id"
            class="flex items-center gap-2 rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-sm"
          >
            <span v-if="att.type === 'image'">📷</span>
            <span v-else>📄</span>
            <span class="max-w-[120px] truncate text-stone-300">{{ att.name }}</span>
            <button @click="removeAttachment(idx)" class="text-stone-500 transition hover:text-red-400">✕</button>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            @click="handleFileSelect"
            :disabled="uploading || attachments.length >= MAX_FILES"
            class="rounded-xl p-3 transition hover:bg-amber-500/10 disabled:opacity-50"
            :title="t('chat.uploadTooltip')"
          >
            <svg class="h-5 w-5 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
            </svg>
          </button>

          <div class="relative">
            <button
              @click="toggleCommands"
              class="rounded-xl p-3 transition hover:bg-amber-500/10"
              :title="t('chat.commandButton')"
            >
              <svg class="h-5 w-5 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </button>
            <div
              v-if="showCommands"
              class="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-2xl border border-amber-100/10 bg-[#171411] p-2 shadow-xl"
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
            @click="sendMessage"
            :disabled="!wsStore.isConnected || (!inputMessage.trim() && attachments.length === 0)"
            class="rounded-2xl bg-amber-500 px-5 py-3 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-stone-700 disabled:text-stone-400"
          >
            {{ t('common.send') }}
          </button>
        </div>
      </footer>
  </div>
</template>
