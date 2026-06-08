<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/auth'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import ReminderBellButton from '@/components/chat/ReminderBellButton.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettingsStore()
const authStore = useAuthStore()
const reminderStore = useReminderNotificationsStore()
const toast = useToast()
const { locale, t, toggleLocale } = useI18n()

const collapsed = ref(false)
const switching = ref(false)
const showModelPopover = ref(false)

onMounted(async () => {
  const saved = localStorage.getItem('left_panel_collapsed')
  if (saved === 'true') collapsed.value = true
  settingsStore.loadModels()
})

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem('left_panel_collapsed', String(collapsed.value))
}

const getProviderLabel = () => {
  if (settingsStore.currentProvider === 'openai_compatible' && settingsStore.currentEndpointId) {
    const ep = settingsStore.endpoints.find((e) => e.id === settingsStore.currentEndpointId)
    return ep?.name || 'OpenAI'
  }
  return 'Ollama'
}

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
    const success = await settingsStore.applyModelSelection('openai_compatible', modelName, endpointId)
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
  return settingsStore.currentModel === modelName && settingsStore.currentProvider === 'ollama'
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
  { name: 'nav.bi', icon: 'bar-chart', path: '/bi', subtitle: 'nav.bi.subtitle' },
  { name: 'nav.insight', icon: 'search', path: '/insight', subtitle: 'nav.insight.subtitle' },
  { name: 'nav.knowledge', icon: 'book', path: '/wiki' },
  { name: 'nav.meeting', icon: 'mic', path: '/meeting' },
  { name: 'nav.orchestration', icon: 'git-branch', path: '/orchestration' },
  { name: 'nav.presales', icon: 'briefcase', path: '/presales' },
  { name: 'nav.admin', icon: 'shield', path: '/admin', adminOnly: true },
  { name: 'nav.settings', icon: 'settings', path: '/settings' }
]

const moduleRouteMap: Record<string, string> = {
  bi: '/bi',
  insight: '/insight',
  // wiki is always visible
  meeting: '/meeting',
  orchestration: '/orchestration',
  presales: '/presales',
}

const visibleNavItems = computed(() =>
  navItems.filter(item => {
    if ('adminOnly' in item && (item as any).adminOnly) {
      return authStore.user?.role === 'admin'
    }
    if (item.path === '/wiki') return true
    const mod = Object.entries(moduleRouteMap).find(([, path]) => item.path === path)
    if (!mod) return true
    const globallyEnabled =
      settingsStore.enabledModules.length === 0 ||
      settingsStore.enabledModules.includes(mod[0])
    if (!globallyEnabled) return false
    if (settingsStore.roleAllowedModules !== null) {
      return settingsStore.roleAllowedModules.includes(mod[0])
    }
    return true
  })
)

const iconMap: Record<string, string> = {
  'message-circle': 'lucide:message-circle',
  'settings': 'lucide:settings',
  'cpu': 'lucide:cpu',
  'database': 'lucide:database',
  'tools': 'lucide:wrench',
  'bar-chart': 'lucide:bar-chart-3',
  'search': 'lucide:search',
  'shield': 'lucide:shield',
  'book': 'lucide:book-open',
  'mic': 'lucide:mic',
  'git-branch': 'lucide:git-branch',
  'briefcase': 'lucide:briefcase',
}

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

const openReminderNotifications = async () => {
  try {
    await reminderStore.openDrawer()
  } catch {}
}
</script>

<template>
  <aside
    class="h-screen bg-[#13100d] border-r border-amber-100/10 flex flex-col transition-all duration-300"
    :class="collapsed ? 'w-12' : 'w-48'"
  >
    <div class="p-3 border-b border-amber-100/10">
      <button
        @click="toggleCollapse"
        class="w-full flex items-center gap-2 px-2 py-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="collapsed ? t('sidebar.expand') : t('sidebar.collapse')"
      >
        <BaseIcon icon="lucide:menu" :size="20" class="shrink-0" />
        <span v-if="!collapsed" class="text-sm font-medium">PortMeta</span>
      </button>
    </div>

    <nav class="p-1.5">
      <ul class="space-y-0.5">
        <li v-for="item in visibleNavItems" :key="item.path">
          <button
            @click="router.push(item.path)"
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors"
            :class="isActive(item.path)
              ? 'bg-amber-600 text-stone-950 shadow-[0_10px_30px_rgba(217,119,6,0.25)]'
              : 'text-stone-400 hover:bg-white/[0.04] hover:text-stone-100'"
            :title="collapsed ? t(item.name) : undefined"
          >
            <BaseIcon :icon="iconMap[item.icon]" :size="16" class="shrink-0" />
            <div v-if="!collapsed" class="min-w-0 text-left">
              <span class="text-sm truncate block">{{ t(item.name) }}</span>
              <span
                v-if="'subtitle' in item && item.subtitle"
                class="text-[10px] truncate block opacity-70"
                :class="isActive(item.path) ? 'text-stone-800' : 'text-stone-500'"
              >
                {{ t(item.subtitle) }}
              </span>
            </div>
          </button>
        </li>
      </ul>
    </nav>

    <div class="flex-1"></div>

    <!-- v4.0.0: 用户登出区 -->
    <div v-if="authStore.isAuthenticated" class="px-2 py-1.5 flex items-center gap-2">
      <span class="w-5 h-5 bg-amber-500/20 rounded-full flex items-center justify-center text-[10px] text-amber-300 flex-shrink-0">
        {{ (authStore.user?.username || 'U')[0].toUpperCase() }}
      </span>
      <span class="text-[10px] text-stone-400 truncate">{{ authStore.user?.username || '' }}</span>
      <button
        @click="authStore.logout()"
        class="ml-auto text-stone-500 hover:text-red-400 transition-colors p-0.5 rounded hover:bg-red-500/10 flex-shrink-0"
        :title="t('sidebar.logout')"
      >
        <BaseIcon icon="lucide:log-out" :size="14" />
      </button>
    </div>

    <div class="p-1.5 border-t border-amber-100/10 flex flex-col gap-0.5">
      <ReminderBellButton
        data-test="sidebar-reminder-bell"
        class="!p-2"
        :unread-count="reminderStore.unreadCount"
        @open="openReminderNotifications"
      />
      <button
        @click="toggleLocale"
        class="w-full flex items-center justify-center p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="locale === 'zh' ? t('common.switchToEnglish') : t('common.switchToChinese')"
      >
        <span class="text-xs font-medium">{{ locale === 'zh' ? 'EN' : 'ZH' }}</span>
      </button>
      <button
        @click="router.push('/models')"
        class="w-full flex items-center justify-center p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="t('sidebar.modelConfigLink')"
        :aria-label="t('sidebar.modelConfigLink')"
      >
        <BaseIcon icon="lucide:cpu" :size="16" />
      </button>
    </div>

    <div v-if="!collapsed" class="border-t border-amber-100/10 p-2.5 relative">
      <button
        @click="showModelPopover = !showModelPopover"
        class="w-full flex items-center justify-between px-2.5 py-2 bg-white/[0.04] hover:bg-white/[0.06] rounded-lg transition-colors text-left"
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
        <BaseIcon icon="lucide:chevron-down" :size="14" class="text-stone-500 shrink-0 transition-transform" :class="showModelPopover ? 'rotate-180' : ''" />
      </button>

      <div v-if="showModelPopover" class="absolute bottom-full left-2 right-2 mb-1 bg-surface-2 border border-amber-100/10 rounded-xl shadow-2xl z-50 overflow-hidden max-h-64 flex flex-col">
        <div class="max-h-48 overflow-y-auto">
          <p class="px-2.5 py-1.5 text-[10px] font-medium text-stone-500 uppercase tracking-wider border-b border-amber-100/10">
            {{ t('sidebar.localModels') }}
          </p>
          <button
            v-for="model in settingsStore.ollamaModels"
            :key="'o-' + model"
            type="button"
            @click="selectOllamaModel(model); showModelPopover = false"
            :disabled="switching"
            class="w-full px-2.5 py-1.5 text-xs text-left flex items-center justify-between transition-colors"
            :class="isCurrentOllamaModel(model) ? 'bg-amber-500/15 border-l-4 border-amber-400 text-stone-100' : 'hover:bg-white/[0.04] text-stone-300 border-l-4 border-transparent'"
          >
            <span class="truncate">{{ model }}</span>
            <BaseIcon v-if="isCurrentOllamaModel(model)" icon="lucide:check" :size="14" class="text-emerald-400 shrink-0 ml-1" />
          </button>

          <template v-for="ep in settingsStore.endpoints" :key="ep.id">
            <div class="border-t border-amber-100/10 mt-0.5 pt-0.5">
              <p class="px-2.5 py-1 text-[10px] font-medium text-stone-400 truncate" :title="ep.base_url">{{ ep.name }}</p>
              <template v-if="ep.models?.length">
                <button
                  v-for="mod in ep.models"
                  :key="ep.id + '-' + mod"
                  type="button"
                  :disabled="switching || !ep.enabled"
                  @click="selectEndpointModel(ep.id, mod); showModelPopover = false"
                  class="w-full px-2.5 py-1 text-xs text-left flex items-center justify-between transition-colors"
                  :class="isCurrentEndpointModel(ep.id, mod) ? 'bg-amber-500/15 border-l-4 border-emerald-400 text-stone-100' : ep.enabled ? 'hover:bg-white/[0.04] text-stone-300 border-l-4 border-transparent' : 'text-stone-600 cursor-not-allowed border-l-4 border-transparent'"
                >
                  <span class="truncate">{{ mod }}</span>
                  <BaseIcon v-if="isCurrentEndpointModel(ep.id, mod)" icon="lucide:check" :size="14" class="text-emerald-400 shrink-0 ml-1" />
                </button>
              </template>
              <p v-else class="px-2.5 py-1.5 text-[10px] text-stone-500">{{ t('sidebar.noEndpointModels') }}</p>
            </div>
          </template>
        </div>
        <button
          type="button"
          @click="router.push('/models'); showModelPopover = false"
          class="w-full px-2.5 py-2 text-xs text-left text-stone-300 border-t border-amber-100/10 hover:bg-white/[0.04] flex items-center gap-1.5 transition-colors shrink-0"
        >
          <BaseIcon icon="lucide:settings" :size="14" />
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
  </aside>
</template>
