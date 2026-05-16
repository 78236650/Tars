<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettingsStore()
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
  { name: 'nav.bi', icon: 'bar-chart', path: '/bi' },
  { name: 'nav.knowledge', icon: 'book', path: '/knowledge' },
  { name: 'nav.meeting', icon: 'mic', path: '/meeting' },
  { name: 'nav.settings', icon: 'settings', path: '/settings' }
]

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    'message-circle': 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
    'settings': 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    'cpu': 'M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z',
    'database': 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3-3.582 3-8 3-8-1.343-8-3zm0 5c0 1.657 3.582 3 8 3s8-1.343 8-3m-16 0v5c0 1.657 3.582 3 8 3s8-1.343 8-3v-5',
    'tools': 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
    'bar-chart': 'M18 20V10M12 20V4M6 20v-6',
    'book': 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
    'mic': 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z'
  }
  return icons[iconName] || icons['message-circle']
}

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
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
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <span v-if="!collapsed" class="text-sm font-medium">TARS</span>
      </button>
    </div>

    <nav class="p-1.5">
      <ul class="space-y-0.5">
        <li v-for="item in navItems" :key="item.path">
          <button
            @click="router.push(item.path)"
            class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors"
            :class="isActive(item.path)
              ? 'bg-amber-600 text-stone-950 shadow-[0_10px_30px_rgba(217,119,6,0.25)]'
              : 'text-stone-400 hover:bg-white/[0.04] hover:text-stone-100'"
            :title="collapsed ? t(item.name) : undefined"
          >
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="getIconPath(item.icon)" />
            </svg>
            <span v-if="!collapsed" class="text-sm truncate">{{ t(item.name) }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <div class="flex-1"></div>

    <div class="p-1.5 border-t border-amber-100/10 flex flex-col gap-0.5">
      <button
        @click="toggleLocale"
        class="w-full flex items-center justify-center p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="locale === 'zh' ? 'Switch to English' : '切换到中文'"
      >
        <span class="text-xs font-medium">{{ locale === 'zh' ? 'EN' : '中' }}</span>
      </button>
      <button
        @click="router.push('/models')"
        class="w-full flex items-center justify-center p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        title="模型设置"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m14 0h2M3 15h2m14 0h2M7 7h10v10H7V7z" />
        </svg>
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
        <svg class="w-3.5 h-3.5 text-stone-500 flex-shrink-0 transition-transform" :class="showModelPopover ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      <div v-if="showModelPopover" class="absolute bottom-full left-2 right-2 mb-1 bg-[#1a1511] border border-amber-100/10 rounded-xl shadow-2xl z-50 overflow-hidden max-h-64 flex flex-col">
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
            <span v-if="isCurrentOllamaModel(model)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
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
                  <span v-if="isCurrentEndpointModel(ep.id, mod)" class="text-emerald-400 text-xs flex-shrink-0 ml-1">✓</span>
                </button>
              </template>
            </div>
          </template>
        </div>
        <button
          type="button"
          @click="router.push('/models'); showModelPopover = false"
          class="w-full px-2.5 py-2 text-xs text-left text-stone-300 border-t border-amber-100/10 hover:bg-white/[0.04] flex items-center gap-1.5 transition-colors shrink-0"
        >
          <span class="text-xs">⚙</span>
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
