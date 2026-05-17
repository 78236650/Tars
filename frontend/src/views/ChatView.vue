<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useChatStore } from '@/stores/chat'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useWsStore } from '@/stores/wsStore'
import { sessionsApi } from '@/api'
import { useI18n } from '@/i18n'
import ChatPanel from '@/components/chat/ChatPanel.vue'

const settingsStore = useSettingsStore()
const chatStore = useChatStore()
const reminderNotificationsStore = useReminderNotificationsStore()
const wsStore = useWsStore()
const { t } = useI18n()
const messages = ref<{ id: string, role: string, content: string, timestamp: string, attachments?: any[], thinking?: any }[]>([])
const inputMessage = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)

const autoResize = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

// 斜杠命令
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

// 文件上传相关
const attachments = ref<{ file_id: string; name: string; type: string; mime_type: string; size: number; preview: string }[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const MAX_FILES = 5
const MAX_SIZE = 50 * 1024 * 1024  // 50MB

// WebSocket 由 wsStore 全局管理，ChatView 订阅消息即可
const setupWsHandler = () => {
  wsStore.connect()

  const wsHandler = {
    onMessage: async (data: any) => {

    if (data.type === 'text_chunk') {
      wsStore.isGenerating = true
      if (chatStore.currentSessionId && data.session_id !== chatStore.currentSessionId) {
        return
      }
      const streamId = `streaming-${data.session_id}`
      const lastMsg = messages.value[messages.value.length - 1]
      // v2.6.1: thinking_start 已创建占位消息，直接追加内容
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === streamId) {
        lastMsg.content += data.content
      }
    } else if (data.type === 'tool_calling') {
    } else if (data.type === 'tool_result') {
      wsStore.isGenerating = true
    } else if (data.type === 'warning') {
      messages.value.push({
        id: Date.now().toString() + '_warn',
        role: 'system',
        content: `⚠️ ${data.message}`,
        timestamp: data.timestamp
      })
    } else if (data.type === 'cron_reminder') {
      const shouldShowInChat = !(
        chatStore.currentSessionId &&
        data.session_id &&
        data.session_id !== chatStore.currentSessionId
      )
      if (shouldShowInChat) {
        messages.value.push({
          id: `${Date.now()}_cron_reminder`,
          role: 'system',
          content: `⏰ ${data.message}`,
          timestamp: data.timestamp
        })
      }
      try {
        await reminderNotificationsStore.refreshAfterRealtimeReminder()
      } catch {}
    } else if (data.type === 'file_processing') {
      // 可选：显示文件处理中状态
    } else if (data.type === 'thinking_start') {
      // v2.6.1: 流式 — 立即创建占位 assistant 消息
      const streamId = `streaming-${data.session_id}`
      messages.value.push({
        id: streamId,
        role: 'assistant',
        content: '',
        timestamp: data.timestamp,
        thinking: { isActive: true, steps: [] }
      })
    } else if (data.type === 'thinking_step') {
      // v2.6.1: 流式 — 追加到当前 assistant 消息的 thinking.steps
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant' && last.thinking) {
        last.thinking.steps.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          step: data.step || '',
          title: data.title || '',
          detail: data.detail,
          timestamp: data.timestamp || ''
        })
      }
    } else if (data.type === 'thinking_complete') {
      // v2.6.1: 标记 thinking 完成
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].role === 'assistant' && (messages.value[i] as any).thinking) {
          (messages.value[i] as any).thinking.isActive = false
          break
        }
      }
    } else if (data.type === 'done') {
      wsStore.isGenerating = false
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.id?.startsWith('streaming-')) {
        lastMsg.id = `msg-${Date.now()}`
      }
    } else if (data.type === 'error') {
      wsStore.isGenerating = false
      messages.value.push({
        id: data.session_id,
        role: 'system',
        content: `Error: ${data.message}`,
        timestamp: data.timestamp
      })
    } else if (data.type === 'generation_start') {
      wsStore.isGenerating = true
    } else if (data.type === 'generation_end') {
      wsStore.isGenerating = false
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.id?.startsWith('streaming-')) {
        lastMsg.id = `msg-${Date.now()}`
      }
    } else if (data.type === 'task_created' || data.type === 'task_updated') {
      // v2.6.1: 内嵌任务卡片，替换独立抽屉
      const t = data.payload?.task || data.task
      if (!t) return
      const existing = messages.value.find(m => (m as any).task?.id === t.id)
      if (existing) {
        (existing as any).task = t
      } else {
        messages.value.push({
          id: `task-${t.id}`,
          role: 'task' as any,
          content: '',
          timestamp: data.timestamp,
          task: t,
        } as any)
      }
    } else if (data.type === 'step_verified' || data.type === 'step_retrying') {
      // 更新任务卡片中的步骤状态
      const taskId = data.task_id
      const taskMsg = messages.value.find(m => (m as any).task?.id === taskId)
      if (!taskMsg || !(taskMsg as any).task) return
      const task = (taskMsg as any).task
      const stepId = data.step_id
      const step = task.steps?.find((s: any) => s.id === stepId || s.step_order === stepId)
      if (step) {
        step.status = data.type === 'step_verified' ? 'completed' : 'running'
        task.current_step = Math.max(task.current_step, (step.step_order || 0))
      }
    } else if (data.type === 'task_completed') {
      const tid = data.payload?.task_id
      if (!tid) return
      const existing = messages.value.find(m => (m as any).task?.id === tid)
      if (existing) {
        (existing as any).task.status = 'completed'
        if (data.payload?.artifacts) (existing as any).task.artifacts = data.payload.artifacts
      }
    } else if (data.type === 'task_aborted') {
      const tid = data.payload?.task_id || data.task_id
      if (!tid) return
      const existing = messages.value.find(m => (m as any).task?.id === tid)
      if (existing) (existing as any).task.status = 'aborted'
    } else if (data.type === 'plan_created') {
      // 保留为聊天消息（不打开抽屉）
      messages.value.push({
        id: `plan_${Date.now()}`,
        role: 'plan',
        content: JSON.stringify(data.plan),
        timestamp: data.timestamp,
        plan: data.plan,
        planSteps: data.plan.steps.map((s: any) => ({ ...s, status: 'pending' })),
      } as any)
    } else if (data.type === 'plan_step_start') {
      const planMsg = [...messages.value].reverse().find((m: any) => m.planSteps)
      if (planMsg && (planMsg as any).planSteps) {
        const step = (planMsg as any).planSteps.find((s: any) => s.id === data.step_id)
        if (step) step.status = 'running'
      }
    } else if (data.type === 'plan_step_complete') {
      const planMsg = [...messages.value].reverse().find((m: any) => m.planSteps)
      if (planMsg && (planMsg as any).planSteps) {
        const step = (planMsg as any).planSteps.find((s: any) => s.id === data.step_id)
        if (step) {
          step.status = data.success ? 'completed' : 'failed'
          step.output = data.output
          step.error = data.error
        }
      }
    } else if (data.type === 'plan_step_failed') {
      const decision = confirm(t('chat.stepFailedConfirm', { stepId: data.step_id, error: data.error }))
      wsStore.send({
        type: 'user_decision',
        session_id: data.session_id,
        step_id: data.step_id,
        decision: decision ? 'retry' : 'abort',
      })
    } else if (data.type === 'plan_complete') {
      wsStore.isGenerating = false
    } else if (data.type === 'command_result') {
      messages.value.push({
        id: Date.now().toString() + '_cmd',
        role: 'system',
        content: data.message,
        timestamp: data.timestamp,
      })
    } else if (data.type === 'session_changed') {
      if (data.new_session_id) {
        chatStore.currentSessionId = data.new_session_id
      }
    } else if (data.type === 'confirmation_required') {
      const ok = confirm(t('chat.confirmationRequired', { message: data.message }))
      wsStore.send({
        type: 'user_decision',
        session_id: data.session_id,
        decision: ok ? 'allow' : 'deny',
      })
    }
    }
  }

  return wsStore.subscribe(wsHandler)
}

const handleFileSelect = () => {
  fileInputRef.value?.click()
}

const onFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return

  for (const file of Array.from(files)) {
    if (attachments.value.length >= MAX_FILES) {
      alert(t('chat.maxFiles'))
      break
    }
    if (file.size > MAX_SIZE) {
      alert(t('chat.fileTooLarge'))
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
      alert(err.detail || t('chat.uploadFailed'))
    }
  } catch (e) {
    alert(t('chat.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

const removeAttachment = (index: number) => {
  attachments.value.splice(index, 1)
}

const loadSessionMessages = async (sessionId: string) => {
  try {
    const history = await sessionsApi.getMessages(sessionId)
    messages.value = history.map(m => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
    }))
  } catch (e) {
    console.error('加载会话历史失败', e)
    messages.value = []
  }
}

const quickStart = (text: string) => {
  inputMessage.value = text
}

const sendMessage = async () => {
  if ((!inputMessage.value.trim() && attachments.value.length === 0) || !wsStore.isConnected) return
  if (!chatStore.currentSessionId) return

  const sessionId = chatStore.currentSessionId
  const messageContent = inputMessage.value
  const isFirstMessage = messages.value.length === 0

  messages.value.push({
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

// 组合式 API 中 setup 顶层调用，组件挂载时执行
const unsubscribe = setupWsHandler()

// 键盘快捷键
const handleKeydown = (e: KeyboardEvent) => {
  const ctrl = e.ctrlKey || e.metaKey
  if (ctrl && e.key === 'Enter') { e.preventDefault(); sendMessage() }
  if (ctrl && (e.key === '/' || e.key === 'k')) { e.preventDefault(); toggleCommands() }
  if (ctrl && e.key === 'l') { e.preventDefault(); inputMessage.value = '/clear'; sendMessage() }
}

onMounted(async () => {
  settingsStore.loadModels()
  await chatStore.initIfEmpty()
  if (chatStore.currentSessionId) {
    await loadSessionMessages(chatStore.currentSessionId)
  }
  try {
    await reminderNotificationsStore.loadList()
  } catch {}
  document.addEventListener('keydown', handleKeydown)
})

watch(() => chatStore.currentSessionId, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await loadSessionMessages(newId)
  } else if (!newId) {
    messages.value = []
  }
})

onUnmounted(() => {
  unsubscribe()
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-[28px] bg-[#14110f]/55">
      <header class="flex items-center justify-between gap-4 border-b border-amber-100/10 px-6 py-4">
        <div class="min-w-0">
          <div class="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-stone-500">
            <span>{{ t('chat.conversation') }}</span>
            <span class="h-1 w-1 rounded-full bg-slate-600"></span>
            <span>{{ chatStore.currentSessionId ? t('chat.liveSession') : t('chat.idleSession') }}</span>
          </div>
          <div class="mt-2 flex items-center gap-3">
            <span class="h-2.5 w-2.5 rounded-full" :class="wsStore.isConnected ? 'bg-emerald-400' : 'bg-rose-400'"></span>
            <p class="text-sm text-stone-300">{{ wsStore.isConnected ? t('chat.connected') : t('chat.disconnected') }}</p>
            <span class="rounded-full border border-amber-100/10 bg-white/[0.04] px-3 py-1 text-xs text-stone-300">
              {{ settingsStore.currentModel || t('chat.notSelectedModel') }}
            </span>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
            @click="quickStart('/plan ')"
          >
            {{ t('chat.planMode') }}
          </button>
          <button
            type="button"
            class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
            @click="quickStart('/brainstorm ')"
          >
            {{ t('chat.brainstormMode') }}
          </button>
        </div>
      </header>

      <ChatPanel :messages="messages" :is-generating="wsStore.isGenerating" @quick-start="quickStart" />

      <footer class="border-t border-amber-100/10 px-6 py-4">
        <!-- 附件预览区 -->
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
          <!-- 文件上传按钮 -->
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

          <!-- 命令按钮 -->
          <div class="relative">
            <button
              @click="toggleCommands"
              class="rounded-xl p-3 transition hover:bg-amber-500/10"
              :title="t('chat.commandButton')"
            >
              <span class="text-lg font-bold text-amber-300">/</span>
            </button>
            <div
              v-if="showCommands"
              class="absolute bottom-full left-0 z-50 mb-2 w-64 overflow-hidden rounded-[20px] border border-amber-100/10 bg-[#171411] shadow-[0_24px_80px_rgba(8,7,5,0.55)]"
            >
              <div class="border-b border-amber-100/10 px-3 py-2 text-xs font-medium text-stone-400">{{ t('chat.commandTitle') }}</div>
              <button
                v-for="cmd in commands"
                :key="cmd.name"
                @click="selectCommand(cmd)"
                class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-amber-500/10"
              >
                <span class="flex-shrink-0 text-sm font-mono text-amber-300">{{ cmd.name }}</span>
                <span class="truncate text-xs text-stone-400">{{ cmd.desc }}</span>
              </button>
            </div>
          </div>
          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept="image/*,.txt,.md,.py,.js,.ts,.json,.yaml,.yml,.pdf,.docx,.xlsx,.csv"
            class="hidden"
            @change="onFileChange"
          />

          <div class="flex-1 relative">
            <textarea
              ref="inputRef"
              v-model="inputMessage"
              @input="autoResize"
              :placeholder="t('chat.placeholder')"
              class="w-full resize-none overflow-hidden rounded-xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 text-white placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
              rows="1"
            ></textarea>
          </div>
          <button
            @click="sendMessage"
            :disabled="(!inputMessage.trim() && attachments.length === 0) || !wsStore.isConnected"
            class="rounded-xl bg-amber-500 px-6 py-3 font-medium text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-stone-700 disabled:text-stone-300"
          >
            {{ t('common.send') }}
          </button>
        </div>
      </footer>
  </div>
</template>
