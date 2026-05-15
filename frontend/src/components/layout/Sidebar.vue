<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettingsStore()
const toast = useToast()
const { locale, t, toggleLocale } = useI18n()
const chatStore = useChatStore()

const collapsed = ref(false)
const searchQuery = ref('')
const switching = ref(false)
const showModelPopover = ref(false)

onMounted(async () => {
  const saved = localStorage.getItem('sidebar_collapsed')
  if (saved === 'true') collapsed.value = true
  settingsStore.loadModels()
  await chatStore.loadSessions()
})

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem('sidebar_collapsed', String(collapsed.value))
}

const getProviderLabel = computed(() => {
  if (
    settingsStore.currentProvider === 'openai_compatible' &&
    settingsStore.currentEndpointId
  ) {
    const ep = settingsStore.endpoints.find((e) => e.id === settingsStore.currentEndpointId)
    return ep?.name || 'OpenAI'
  }
  return 'Ollama'
})

const selectOllamaModel = async (modelName: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.applyModelSelection('ollama', modelName)
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${modelName}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } catch {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    switching.value = false
  }
}

const selectEndpointModel = async (endpointId: string, modelName: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.applyModelSelection(
      'openai_compatible',
      modelName,
      endpointId
    )
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${modelName}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } catch {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    switching.value = false
  }
}

const isCurrentOllamaModel = (modelName: string) => {
  return (
    settingsStore.currentModel === modelName &&
    settingsStore.currentProvider === 'ollama'
  )
}

const isCurrentEndpointModel = (endpointId: string, modelName: string) => {
  return (
    settingsStore.currentProvider === 'openai_compatible' &&
    settingsStore.currentEndpointId === endpointId &&
    settingsStore.currentModel === modelName
  )
}

const navItems = [
  { name: 'nav.chat', icon: 'message-circle', path: '/' },
  { name: 'nav.models', icon: 'cpu', path: '/models' },
  { name: 'nav.tools', icon: 'tools', path: '/tools' },
  { name: 'nav.settings', icon: 'settings', path: '/settings' }
]

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    'message-circle': 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
    'settings': 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    'cpu': 'M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z',
    'tools': 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z'
  }
  return icons[iconName] || icons['message-circle']
}

const isActive = (path: string) => route.path === path

const newChat = async () => {
  await chatStore.createSession()
}

const switchSession = (id: string) => {
  chatStore.switchSession(id)
}

const deleteSession = async (id: string, e: Event) => {
  e.stopPropagation()
  if (!confirm(t('chat.deleteConfirm'))) return
  try {
    await chatStore.deleteSession(id)
    toast.success(t('chat.sessionDeleted'))
  } catch (err) {
    toast.error('Failed')
  }
}

const truncateTitle = (s: string, n = 22) => s.length > n ? s.slice(0, n) + '...' : s

const groupedSessions = computed(() => {
  let list = chatStore.sessions
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(s => s.title?.toLowerCase().includes(q))
  }
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  
  const groups: { label: string; items: typeof list }[] = []
  const todayItems: typeof list = []
  const yesterdayItems: typeof list = []
  const olderItems: typeof list = []
  
  for (const s of list) {
    const d = s.updated_at ? new Date(s.updated_at) : new Date()
    if (d >= today) todayItems.push(s)
    else if (d >= yesterday) yesterdayItems.push(s)
    else olderItems.push(s)
  }
  
  if (todayItems.length) groups.push({ label: '今天', items: todayItems })
  if (yesterdayItems.length) groups.push({ label: '昨天', items: yesterdayItems })
  if (olderItems.length) groups.push({ label: '更早', items: olderItems })
  return groups
})

</script>

<template>
  <aside
    class="h-screen bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-64'"
  >
    <div class="p-4 border-b border-slate-700">
      <div class="flex items-center gap-3">
        <img src="/logo.png" alt="TARS" class="w-10 h-10 rounded-xl object-cover shrink-0" />
        <div v-if="!collapsed" class="overflow-hidden">
          <h1 class="text-lg font-semibold text-white truncate">TARS Agent</h1>
          <p class="text-sm text-slate-400">AI Assistant</p>
        </div>
      </div>
    </div>

    <nav class="p-2">
      <ul class="space-y-1">
        <li v-for="item in navItems" :key="item.path">
          <button
            @click="router.push(item.path)"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
            :class="isActive(item.path)
              ? 'bg-blue-600 text-white'
              : 'text-slate-400 hover:bg-slate-700 hover:text-white'"
            :title="collapsed ? t(item.name) : undefined"
          >
            <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="getIconPath(item.icon)" />
            </svg>
            <span v-if="!collapsed" class="truncate">{{ t(item.name) }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <!-- Session list - expanded mode -->
    <div v-if="!collapsed" class="border-t border-slate-700 flex flex-col flex-1 min-h-0" >
      <div class="p-2 space-y-2">
        <button
          @click="newChat"
          class="w-full px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm flex items-center justify-center gap-2 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {{ t('chat.newChat') }}
        </button>
        <div class="relative">
          <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索会话..."
            class="w-full pl-8 pr-3 py-1.5 bg-slate-700/50 border border-slate-600 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      <div class="overflow-y-auto px-2 pb-2 flex-1">
        <p v-if="chatStore.sessions.length === 0" class="text-xs text-slate-500 text-center py-4">
          {{ t('chat.noSessions') }}
        </p>
        <template v-for="group in groupedSessions" :key="group.label">
          <p class="text-[10px] text-slate-500 font-medium px-2 py-1.5 uppercase tracking-wider">{{ group.label }}</p>
          <button
            v-for="session in group.items"
            :key="session.id"
            @click="switchSession(session.id)"
            class="group w-full px-3 py-2 mb-0.5 rounded-lg text-left text-sm flex items-center justify-between transition-colors"
            :class="chatStore.currentSessionId === session.id
              ? 'bg-blue-600 text-white'
              : 'text-slate-300 hover:bg-slate-700'"
          >
            <span class="truncate flex-1">{{ truncateTitle(session.title) }}</span>
            <span
              @click="deleteSession(session.id, $event)"
              class="opacity-0 group-hover:opacity-100 ml-2 text-slate-400 hover:text-red-400 transition-opacity cursor-pointer"
            >
              &times;
            </span>
          </button>
        </template>
      </div>
    </div>

    <!-- Session list - collapsed mode -->
    <div v-else class="border-t border-slate-700 p-2 flex-1">
      <button
        @click="newChat"
        class="w-full p-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center"
        :title="t('chat.newChat')"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>

    <div class="p-2 border-t border-slate-700 flex flex-col gap-1">
      <button
        @click="toggleLocale"
        class="w-full flex items-center justify-center p-2 text-slate-400 hover:bg-slate-700 hover:text-white rounded-lg transition-colors"
        :title="locale === 'zh' ? 'Switch to English' : '切换到中文'"
      >
        <span class="text-sm">{{ locale === 'zh' ? 'EN' : '中' }}</span>
      </button>
      <button
        @click="toggleCollapse"
        class="w-full flex items-center justify-center p-2 text-slate-400 hover:bg-slate-700 hover:text-white rounded-lg transition-colors"
        :title="collapsed ? t('sidebar.expand') : t('sidebar.collapse')"
      >
        <svg class="w-5 h-5 transition-transform" :class="collapsed ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
      </button>
    </div>

    <!-- 模型选择 Popover（瘦身版） -->
    <div v-if="!collapsed" class="border-t border-slate-700 p-3 relative">
      <button
        @click="showModelPopover = !showModelPopover"
        class="w-full flex items-center justify-between px-3 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
            :class="{
              'bg-emerald-400': settingsStore.currentProvider === 'openai_compatible',
              'bg-blue-400': settingsStore.currentProvider === 'ollama',
            }"
          ></span>
          <span class="text-xs text-slate-300 truncate">{{ settingsStore.currentModel || t('common.loading') }}</span>
        </div>
        <svg class="w-4 h-4 text-slate-500 flex-shrink-0 transition-transform" :class="showModelPopover ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      <!-- Popover -->
      <div v-if="showModelPopover" class="absolute bottom-full left-3 right-3 mb-1 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50 overflow-hidden max-h-72 flex flex-col">
        <div class="max-h-56 overflow-y-auto">
          <p class="px-3 py-2 text-[10px] font-medium text-slate-500 uppercase tracking-wider border-b border-slate-700/80">
            {{ t('sidebar.localModels') }}
          </p>
          <button
            v-for="model in settingsStore.ollamaModels"
            :key="'o-' + model"
            type="button"
            @click="selectOllamaModel(model); showModelPopover = false"
            :disabled="switching"
            class="w-full px-3 py-2 text-sm text-left flex items-center justify-between transition-colors"
            :class="isCurrentOllamaModel(model) ? 'bg-slate-600 border-l-4 border-blue-400 text-white' : 'hover:bg-slate-600/50 text-slate-300 border-l-4 border-transparent'"
          >
            <span class="truncate">{{ model }}</span>
            <span v-if="isCurrentOllamaModel(model)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
          </button>

          <template v-for="ep in settingsStore.endpoints" :key="ep.id">
            <div class="border-t border-slate-700 mt-1 pt-1">
              <p class="px-3 py-1.5 text-[10px] font-medium text-slate-400 truncate" :title="ep.base_url">{{ ep.name }}</p>
              <template v-if="ep.models?.length">
                <button
                  v-for="mod in ep.models"
                  :key="ep.id + '-' + mod"
                  type="button"
                  :disabled="switching || !ep.enabled"
                  @click="selectEndpointModel(ep.id, mod); showModelPopover = false"
                  class="w-full px-3 py-1.5 text-sm text-left flex items-center justify-between transition-colors"
                  :class="isCurrentEndpointModel(ep.id, mod) ? 'bg-slate-600 border-l-4 border-emerald-400 text-white' : ep.enabled ? 'hover:bg-slate-600/50 text-slate-300 border-l-4 border-transparent' : 'text-slate-600 cursor-not-allowed border-l-4 border-transparent'"
                >
                  <span class="truncate">{{ mod }}</span>
                  <span v-if="isCurrentEndpointModel(ep.id, mod)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
                </button>
              </template>
              <p v-else class="px-3 py-2 text-xs text-slate-500">{{ t('sidebar.noEndpointModels') }}</p>
            </div>
          </template>
        </div>
        <button
          type="button"
          @click="router.push('/models'); showModelPopover = false"
          class="w-full px-3 py-2.5 text-sm text-left text-slate-300 border-t border-slate-700 hover:bg-slate-700/60 flex items-center gap-2 transition-colors shrink-0"
        >
          <span class="text-base">⚙</span>
          <span>{{ t('sidebar.modelConfigLink') }}</span>
        </button>
      </div>
    </div>

    <div v-else class="p-2 border-t border-slate-700">
      <div class="text-center">
        <span class="w-1.5 h-1.5 rounded-full inline-block"
          :class="{
            'bg-emerald-400': settingsStore.currentProvider === 'openai_compatible',
            'bg-blue-400': settingsStore.currentProvider === 'ollama',
          }"
        ></span>
      </div>
    </div>
  </aside>

  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="t in toast.toasts.value"
          :key="t.id"
          class="px-4 py-3 rounded-lg shadow-lg min-w-64 max-w-96 flex items-center gap-3"
          :class="{
            'bg-green-600 text-white': t.type === 'success',
            'bg-red-600 text-white': t.type === 'error',
            'bg-blue-600 text-white': t.type === 'info'
          }"
        >
          <span v-if="t.type === 'success'" class="text-lg">✓</span>
          <span v-else-if="t.type === 'error'" class="text-lg">✕</span>
          <span v-else class="text-lg">ℹ</span>
          <span class="text-sm">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  animation: toast-in 0.3s ease-out;
}
.toast-leave-active {
  animation: toast-out 0.3s ease-in;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100px);
  }
}
</style>
