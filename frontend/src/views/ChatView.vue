<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useChatStore } from '@/stores/chat'
import { sessionsApi } from '@/api'
import { useI18n } from '@/i18n'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import Sidebar from '@/components/layout/Sidebar.vue'

const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const chatStore = useChatStore()
const { t } = useI18n()
const messages = ref<{ id: string, role: string, content: string, timestamp: string, attachments?: any[] }[]>([])
const inputMessage = ref('')
const isConnected = ref(false)
const isGenerating = ref(false)
let ws: WebSocket | null = null

// 文件上传相关
const attachments = ref<{ file_id: string; name: string; type: string; mime_type: string; size: number; preview: string }[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const MAX_FILES = 5
const MAX_SIZE = 20 * 1024 * 1024

const connectWebSocket = () => {
  if (ws) return

  ws = new WebSocket(`ws://localhost:8000/ws`)

  ws.onopen = () => {
    isConnected.value = true
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'text_chunk') {
      isGenerating.value = true
      if (chatStore.currentSessionId && data.session_id !== chatStore.currentSessionId) {
        return
      }
      const streamId = `streaming-${data.session_id}`
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === streamId) {
        lastMsg.content += data.content
      } else {
        messages.value.push({
          id: streamId,
          role: 'assistant',
          content: data.content,
          timestamp: data.timestamp,
        })
      }
    } else if (data.type === 'tool_calling') {
      console.log('[ChatView] 工具调用:', data.tool, data.parameters)
    } else if (data.type === 'tool_result') {
      isGenerating.value = true
      const toolMsg = {
        id: data.session_id + '_tool',
        role: 'assistant',
        content: `🔧 ${data.tool}: ${data.output || data.error || '执行完成'}`,
        timestamp: data.timestamp
      }
      const existingToolMsg = messages.value.find(m => m.id === toolMsg.id)
      if (existingToolMsg) {
        existingToolMsg.content = toolMsg.content
      } else {
        messages.value.push(toolMsg)
      }
    } else if (data.type === 'warning') {
      messages.value.push({
        id: Date.now().toString() + '_warn',
        role: 'system',
        content: `⚠️ ${data.message}`,
        timestamp: data.timestamp
      })
    } else if (data.type === 'file_processing') {
      // 可选：显示文件处理中状态
    } else if (data.type === 'done') {
      isGenerating.value = false
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.id?.startsWith('streaming-')) {
        lastMsg.id = `msg-${Date.now()}`
      }
    } else if (data.type === 'error') {
      isGenerating.value = false
      messages.value.push({
        id: data.session_id,
        role: 'system',
        content: `Error: ${data.message}`,
        timestamp: data.timestamp
      })
    } else if (data.type === 'generation_start') {
      isGenerating.value = true
    } else if (data.type === 'generation_end') {
      isGenerating.value = false
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.id?.startsWith('streaming-')) {
        lastMsg.id = `msg-${Date.now()}`
      }
    } else if (data.type === 'plan_created') {
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
      const decision = confirm(`步骤 ${data.step_id} 失败: ${data.error}\n\n点击确定重试，取消中止`)
      ws?.send(JSON.stringify({
        type: 'user_decision',
        session_id: data.session_id,
        step_id: data.step_id,
        decision: decision ? 'retry' : 'abort',
      }))
    } else if (data.type === 'plan_complete') {
      isGenerating.value = false
    } else if (data.type === 'confirmation_required') {
      const ok = confirm(`需要确认:\n${data.message}`)
      ws?.send(JSON.stringify({
        type: 'user_decision',
        session_id: data.session_id,
        decision: ok ? 'allow' : 'deny',
      }))
    }
  }

  ws.onclose = () => {
    isConnected.value = false
    isGenerating.value = false
    ws = null
    setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = () => {
    isConnected.value = false
  }
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

const sendMessage = async () => {
  if ((!inputMessage.value.trim() && attachments.value.length === 0) || !ws) return
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

  isGenerating.value = true

  const payload: any = {
    session_id: sessionId,
    content: messageContent,
  }
  if (attachments.value.length > 0) {
    payload.file_ids = attachments.value.map(a => a.file_id)
  }

  ws.send(JSON.stringify(payload))

  inputMessage.value = ''
  attachments.value = []

  if (isFirstMessage && messageContent.trim()) {
    const newTitle = messageContent.trim().slice(0, 30)
    try {
      await chatStore.updateTitle(sessionId, newTitle)
    } catch (e) {
      console.error('更新标题失败', e)
    }
  }
}

onMounted(async () => {
  settingsStore.loadModels()
  await chatStore.initIfEmpty()
  if (chatStore.currentSessionId) {
    await loadSessionMessages(chatStore.currentSessionId)
  }
  connectWebSocket()
})

watch(() => chatStore.currentSessionId, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await loadSessionMessages(newId)
  } else if (!newId) {
    messages.value = []
  }
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<template>
  <div class="flex h-screen bg-slate-900">
    <Sidebar />
    <main class="flex-1 flex flex-col">
      <header class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-lg">T</span>
          </div>
          <div>
            <h1 class="text-lg font-semibold text-white">TARS Agent</h1>
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full" :class="isConnected ? 'bg-green-500' : 'bg-red-500'"></span>
              <span class="text-sm text-slate-400">{{ isConnected ? t('chat.connected') : t('chat.disconnected') }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
            <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z"/>
            </svg>
            <span class="text-sm text-slate-300">{{ settingsStore.currentModel || t('common.loading') }}</span>
            <span class="text-xs px-1.5 py-0.5 bg-blue-600/30 text-blue-400 rounded">
              {{ settingsStore.currentProvider.startsWith('custom:') ? 'Custom' : settingsStore.currentProvider.toUpperCase() }}
            </span>
          </div>
          <button 
            @click="router.push('/settings')"
            class="p-2 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </button>
        </div>
      </header>
      
      <ChatPanel :messages="messages" :is-generating="isGenerating" />

      <footer class="px-6 py-4 border-t border-slate-700">
        <!-- 附件预览区 -->
        <div v-if="attachments.length > 0" class="mb-3 flex flex-wrap gap-2">
          <div
            v-for="(att, idx) in attachments"
            :key="att.file_id"
            class="flex items-center gap-2 px-3 py-1.5 bg-slate-800 border border-slate-600 rounded-lg text-sm"
          >
            <span v-if="att.type === 'image'">📷</span>
            <span v-else>📄</span>
            <span class="text-slate-300 max-w-[120px] truncate">{{ att.name }}</span>
            <button @click="removeAttachment(idx)" class="text-slate-400 hover:text-red-400">✕</button>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <!-- 文件上传按钮 -->
          <button
            @click="handleFileSelect"
            :disabled="uploading || attachments.length >= MAX_FILES"
            class="p-3 rounded-xl hover:bg-slate-700 disabled:opacity-50 transition-colors"
            :title="t('chat.uploadTooltip')"
          >
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
            </svg>
          </button>
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
              v-model="inputMessage"
              @keydown.enter.exact.prevent="sendMessage"
              :placeholder="t('chat.placeholder')"
              class="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows="1"
            ></textarea>
          </div>
          <button
            @click="sendMessage"
            :disabled="(!inputMessage.trim() && attachments.length === 0) || !isConnected"
            class="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-xl text-white font-medium transition-colors"
          >
            Send
          </button>
        </div>
      </footer>
    </main>
  </div>
</template>