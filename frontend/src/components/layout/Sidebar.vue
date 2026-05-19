<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettingsStore()
const authStore = useAuthStore()
const toast = useToast()
/** 模板中嵌套 ref 需显式列表，避免 v-for 源为 undefined / Ref 导致整页渲染失败 */
const toastItems = computed(() => toast.toasts.value)
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
  { name: 'nav.memory', icon: 'database', path: '/memory' },
  { name: 'nav.models', icon: 'cpu', path: '/models' },
  { name: 'nav.tools', icon: 'tools', path: '/tools' },
  { name: 'nav.bi', icon: 'bar-chart', path: '/bi' },
  { name: 'nav.insight', icon: 'search', path: '/insight' },
  { name: 'nav.knowledge', icon: 'book', path: '/knowledge' },
  { name: 'nav.meeting', icon: 'mic', path: '/meeting' },
  { name: 'nav.admin', icon: 'shield', path: '/admin', adminOnly: true },
  { name: 'nav.settings', icon: 'settings', path: '/settings' }
]

// v4.0.0: 根据模块启用状态过滤导航项
const moduleRouteMap: Record<string, string> = {
  bi: '/bi',
  insight: '/insight',
  knowledge: '/knowledge',
  meeting: '/meeting',
}

const visibleNavItems = computed(() =>
  navItems.filter(item => {
    // Admin only 路由
    if ('adminOnly' in item && (item as any).adminOnly) {
      return authStore.user?.role === 'admin'
    }
    // 模块路由过滤
    const mod = Object.entries(moduleRouteMap).find(([, path]) => item.path === path)
    if (!mod) return true // 核心路由始终显示
    // v4.0.0: 检查全局模块开关
    const globallyEnabled = settingsStore.enabledModules.length === 0 || settingsStore.enabledModules.includes(mod[0])
    if (!globallyEnabled) return false
    // v4.0.2: 检查角色模板模块权限（roleAllowedModules 为 null 时不限制）
    if (settingsStore.roleAllowedModules !== null) {
      return settingsStore.roleAllowedModules.includes(mod[0])
    }
    return true
  })
)

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    'message-circle': 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
    'settings': 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    'cpu': 'M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z',
    'database': 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3-3.582 3-8 3-8-1.343-8-3zm0 5c0 1.657 3.582 3 8 3s8-1.343 8-3m-16 0v5c0 1.657 3.582 3 8 3s8-1.343 8-3v-5',
    'tools': 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
    'bar-chart': 'M18 20V10M12 20V4M6 20v-6',
    'search': 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
    'shield': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    'book': 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    'mic': 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z'
  }
  return icons[iconName] || icons['message-circle']
}

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

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
    toast.error(t('common.deleteFailed'))
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
  
  if (todayItems.length) groups.push({ label: t('sidebar.today'), items: todayItems })
  if (yesterdayItems.length) groups.push({ label: t('sidebar.yesterday'), items: yesterdayItems })
  if (olderItems.length) groups.push({ label: t('sidebar.earlier'), items: olderItems })
  return groups
})

</script>

<template>
  <aside
    class="h-screen bg-[#13100d] border-r border-amber-100/10 flex flex-col transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-64'"
  >
    <div class="p-4 border-b border-amber-100/10">
      <div v-if="!collapsed" class="overflow-hidden">
        <h1 class="text-xl font-bold tracking-wide text-amber-400">TARS</h1>
        <p class="text-xs text-stone-500 mt-0.5">{{ t('sidebar.assistantSubtitle') }}</p>
      </div>
      <div v-else class="flex justify-center">
        <span class="text-lg font-bold text-amber-400">T</span>
      </div>
    </div>

    <nav class="p-2">
      <ul class="space-y-1">
        <li v-for="item in visibleNavItems" :key="item.path">
          <button
            @click="router.push(item.path)"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
            :class="isActive(item.path)
              ? 'bg-amber-600 text-stone-950 shadow-[0_10px_30px_rgba(217,119,6,0.25)]'
              : 'text-stone-400 hover:bg-white/[0.04] hover:text-stone-100'"
            :title="collapsed ? t(item.name) : undefined"
          >
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="getIconPath(item.icon)" />
            </svg>
            <span v-if="!collapsed" class="truncate">{{ t(item.name) }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <!-- 用户登出区 v4.0.0 -->
    <div v-if="authStore.isAuthenticated" class="border-t border-amber-100/10 px-3 py-2 shrink-0">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <span class="w-6 h-6 bg-amber-500/20 rounded-full flex items-center justify-center text-xs text-amber-300 flex-shrink-0">
            {{ (authStore.user?.username || 'U')[0].toUpperCase() }}
          </span>
          <span class="text-xs text-stone-400 truncate">{{ authStore.user?.username || '' }}</span>
        </div>
        <button
          @click="authStore.logout(); router.push('/login')"
          class="text-[10px] text-stone-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10 flex-shrink-0"
          :title="t('sidebar.logout')"
        >
          ⏻
        </button>
      </div>
    </div>

    <!-- Session list - expanded mode -->
    <div v-if="!collapsed" class="border-t border-amber-100/10 flex flex-col flex-1 min-h-0" >
      <div class="p-3 space-y-2">
        <button
          @click="newChat"
          class="w-full px-3 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-stone-950 text-sm font-medium flex items-center justify-center gap-2 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {{ t('chat.newChat') }}
        </button>
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('sidebar.searchSessions')"
            class="w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-amber-100/10 rounded-lg text-sm text-stone-100 placeholder-stone-500 focus:outline-none focus:border-amber-400 focus:bg-white/[0.06] transition-colors"
          />
        </div>
      </div>

      <div class="overflow-y-auto px-3 pb-3 flex-1">
        <p v-if="chatStore.sessions.length === 0" class="text-sm text-stone-500 text-center py-8">
          {{ t('chat.noSessions') }}
        </p>
        <template v-for="group in groupedSessions" :key="group.label">
          <div class="flex items-center gap-3 py-2 mt-2 first:mt-0">
            <span class="text-xs font-semibold text-stone-400 uppercase tracking-wide">{{ group.label }}</span>
            <div class="flex-1 h-px bg-amber-100/10"></div>
            <span class="text-xs text-stone-600">{{ group.items.length }}</span>
          </div>
          <button
            v-for="session in group.items"
            :key="session.id"
            @click="switchSession(session.id)"
            class="group w-full px-3 py-2.5 mb-1 rounded-lg text-left text-sm flex items-center justify-between transition-all duration-150"
            :class="chatStore.currentSessionId === session.id
              ? 'bg-amber-500/15 border-l-4 border-amber-500 text-stone-100 font-medium shadow-sm'
              : 'text-stone-300 hover:bg-white/[0.04] border-l-4 border-transparent'"
          >
            <span class="truncate flex-1 mr-2">{{ truncateTitle(session.title) }}</span>
            <span
              @click="deleteSession(session.id, $event)"
              class="opacity-0 group-hover:opacity-100 flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-stone-400 hover:text-red-300 hover:bg-white/[0.06] transition-all cursor-pointer"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </span>
          </button>
        </template>
      </div>
    </div>

    <!-- Session list - collapsed mode -->
    <div v-else class="border-t border-amber-100/10 p-1.5 flex-1 flex flex-col gap-1">
      <button
        @click="newChat"
        class="w-full p-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-stone-950 flex items-center justify-center"
        :title="t('chat.newChat')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
      <button
        @click="router.push('/settings')"
        class="w-full p-2 rounded-lg text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 flex items-center justify-center transition-colors"
        :title="t('nav.settings')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
      <button
        @click="router.push('/models')"
        class="w-full p-2 rounded-lg text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 flex items-center justify-center transition-colors"
        :title="t('nav.models')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z" />
        </svg>
      </button>
      <button
        @click="toggleLocale"
        class="w-full p-2 rounded-lg text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 flex items-center justify-center transition-colors"
        :title="locale === 'zh' ? t('common.switchToEnglish') : t('common.switchToChinese')"
      >
        <span class="text-xs font-medium">{{ locale === 'zh' ? 'EN' : 'ZH' }}</span>
      </button>
    </div>

    <div class="p-1.5 border-t border-amber-100/10 flex flex-col gap-1">
      <button
        @click="toggleCollapse"
        class="w-full flex items-center justify-center p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="collapsed ? t('sidebar.expand') : t('sidebar.collapse')"
      >
        <svg class="w-4 h-4 transition-transform" :class="collapsed ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
      </button>
    </div>

    <!-- 模型选择 Popover（瘦身版） -->
    <div v-if="!collapsed" class="border-t border-amber-100/10 p-3 relative">
      <button
        @click="showModelPopover = !showModelPopover"
        class="w-full flex items-center justify-between px-3 py-2 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg transition-colors"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
            :class="{
              'bg-emerald-400': settingsStore.currentProvider === 'openai_compatible',
              'bg-blue-400': settingsStore.currentProvider === 'ollama',
            }"
          ></span>
          <span class="text-xs text-stone-300 truncate">{{ settingsStore.currentModel || t('common.loading') }}</span>
        </div>
        <svg class="w-4 h-4 text-stone-500 flex-shrink-0 transition-transform" :class="showModelPopover ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      <!-- Popover -->
      <div v-if="showModelPopover" class="absolute bottom-full left-3 right-3 mb-1 bg-[#1a1511] border border-amber-100/10 rounded-xl shadow-2xl z-50 overflow-hidden max-h-72 flex flex-col">
        <div class="max-h-56 overflow-y-auto">
          <p class="px-3 py-2 text-[10px] font-medium text-stone-500 uppercase tracking-wider border-b border-amber-100/10">
            {{ t('sidebar.localModels') }}
          </p>
          <button
            v-for="model in settingsStore.ollamaModels"
            :key="'o-' + model"
            type="button"
            @click="selectOllamaModel(model); showModelPopover = false"
            :disabled="switching"
            class="w-full px-3 py-2 text-sm text-left flex items-center justify-between transition-colors"
            :class="isCurrentOllamaModel(model) ? 'bg-amber-500/15 border-l-4 border-amber-400 text-stone-100' : 'hover:bg-white/[0.04] text-stone-300 border-l-4 border-transparent'"
          >
            <span class="truncate">{{ model }}</span>
            <span v-if="isCurrentOllamaModel(model)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
          </button>

          <template v-for="ep in settingsStore.endpoints" :key="ep.id">
            <div class="border-t border-amber-100/10 mt-1 pt-1">
              <p class="px-3 py-1.5 text-[10px] font-medium text-stone-400 truncate" :title="ep.base_url">{{ ep.name }}</p>
              <template v-if="ep.models?.length">
                <button
                  v-for="mod in ep.models"
                  :key="ep.id + '-' + mod"
                  type="button"
                  :disabled="switching || !ep.enabled"
                  @click="selectEndpointModel(ep.id, mod); showModelPopover = false"
                  class="w-full px-3 py-1.5 text-sm text-left flex items-center justify-between transition-colors"
                  :class="isCurrentEndpointModel(ep.id, mod) ? 'bg-amber-500/15 border-l-4 border-emerald-400 text-stone-100' : ep.enabled ? 'hover:bg-white/[0.04] text-stone-300 border-l-4 border-transparent' : 'text-stone-600 cursor-not-allowed border-l-4 border-transparent'"
                >
                  <span class="truncate">{{ mod }}</span>
                  <span v-if="isCurrentEndpointModel(ep.id, mod)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
                </button>
              </template>
              <p v-else class="px-3 py-2 text-xs text-stone-500">{{ t('sidebar.noEndpointModels') }}</p>
            </div>
          </template>
        </div>
        <button
          type="button"
          @click="router.push('/models'); showModelPopover = false"
          class="w-full px-3 py-2.5 text-sm text-left text-stone-300 border-t border-amber-100/10 hover:bg-white/[0.04] flex items-center gap-2 transition-colors shrink-0"
        >
          <span class="text-base">⚙</span>
          <span>{{ t('sidebar.modelConfigLink') }}</span>
        </button>
      </div>
    </div>

    <div v-else class="p-2 border-t border-amber-100/10">
      <div class="text-center">
        <span class="w-1.5 h-1.5 rounded-full inline-block"
          :class="{
            'bg-emerald-400': settingsStore.currentProvider === 'openai_compatible',
            'bg-blue-400': settingsStore.currentProvider === 'ollama',
          }"
        ></span>
      </div>
    </div>

    <!-- v4.0.0: Version -->
    <div class="border-t border-amber-100/10 px-3 py-2.5 shrink-0">
      <p class="text-[10px] text-stone-500 text-center tracking-[0.18em] select-none">{{ t('sidebar.version') }}</p>
    </div>
  </aside>

  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="toastItem in toastItems"
          :key="toastItem.id"
          class="px-4 py-3 rounded-lg shadow-lg min-w-64 max-w-96 flex items-center gap-3"
          :class="{
            'bg-green-600 text-white': toastItem.type === 'success',
            'bg-red-600 text-white': toastItem.type === 'error',
            'bg-blue-600 text-white': toastItem.type === 'info'
          }"
        >
          <span v-if="toastItem.type === 'success'" class="text-lg">✓</span>
          <span v-else-if="toastItem.type === 'error'" class="text-lg">✕</span>
          <span v-else class="text-lg">ℹ</span>
          <span class="text-sm">{{ toastItem.message }}</span>
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
