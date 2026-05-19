<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useWsStore } from '@/stores/wsStore'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const wsStore = useWsStore()
const reminderStore = useReminderNotificationsStore()
const toast = useToast()
const { t, locale } = useI18n()

const collapsed = ref(false)
const searchQuery = ref('')

onMounted(async () => {
  const saved = localStorage.getItem('right_panel_collapsed')
  if (saved === 'true') collapsed.value = true
  await chatStore.loadSessions()
})

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem('right_panel_collapsed', String(collapsed.value))
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
  } catch {
    toast.error(t('common.deleteFailed'))
  }
}

const truncateTitle = (s: string, n = 18) => s.length > n ? s.slice(0, n) + '...' : s

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

const sessionCount = computed(() => chatStore.sessions.length)
const connectionStatus = computed(() => wsStore.isConnected ? t('chat.connected') : t('chat.disconnected'))
const unreadCount = computed(() => reminderStore.unreadCount)

const copyConversation = async () => {
  const messages = chatStore.currentSessionId
  if (!messages) {
    toast.info(t('rightPanel.noCurrentSession'))
    return
  }
  toast.info(t('rightPanel.copied'))
}

const exportConversation = () => {
  toast.info(t('rightPanel.exportComingSoon'))
}

const clearConversation = () => {
  if (!confirm(t('rightPanel.clearConfirm'))) return
  chatStore.switchSession(chatStore.sessions[0]?.id || '')
  toast.success(t('rightPanel.cleared'))
}
</script>

<template>
  <aside
    class="h-screen flex flex-col transition-all duration-300 bg-[#110f0d]/96 border-l border-amber-100/10"
    :class="collapsed ? 'w-12' : 'w-64'"
  >
    <div class="p-3 border-b border-amber-100/10 flex items-center justify-between">
      <button
        v-if="!collapsed"
        @click="toggleCollapse"
        class="flex items-center gap-2 px-2 py-1.5 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors"
        :title="t('sidebar.collapse')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
        <span class="text-xs">{{ t('rightPanel.collapse') }}</span>
      </button>
      <button
        v-else
        @click="toggleCollapse"
        class="w-full p-2 text-stone-400 hover:bg-white/[0.04] hover:text-stone-100 rounded-lg transition-colors flex justify-center"
        :title="t('sidebar.expand')"
      >
        <svg class="w-4 h-4 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
    </div>

    <template v-if="!collapsed">
      <div class="flex-1 overflow-hidden flex flex-col">
        <div class="p-3 space-y-2 border-b border-amber-100/10">
          <button
            @click="newChat"
            class="w-full px-3 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-stone-950 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              :placeholder="t('sidebar.searchSessions')"
              class="w-full pl-8 pr-2 py-1.5 bg-white/[0.04] border border-amber-100/10 rounded-lg text-xs text-stone-100 placeholder-stone-500 focus:outline-none focus:border-amber-400 focus:bg-white/[0.06] transition-colors"
            />
          </div>
        </div>

        <div class="flex-1 overflow-y-auto px-2 py-2">
          <p v-if="chatStore.sessions.length === 0" class="text-xs text-stone-500 text-center py-6">
            {{ t('chat.noSessions') }}
          </p>
          <template v-for="group in groupedSessions" :key="group.label">
            <div class="flex items-center gap-2 py-1.5 mt-1 first:mt-0">
              <span class="text-[10px] font-semibold text-stone-500 uppercase tracking-wide">{{ group.label }}</span>
              <div class="flex-1 h-px bg-amber-100/10"></div>
              <span class="text-[10px] text-stone-600">{{ group.items.length }}</span>
            </div>
            <button
              v-for="session in group.items"
              :key="session.id"
              @click="switchSession(session.id)"
              class="group w-full px-2.5 py-2 mb-0.5 rounded-lg text-left text-xs flex items-center justify-between transition-all duration-150"
              :class="chatStore.currentSessionId === session.id
                ? 'bg-amber-500/15 border-l-4 border-amber-500 text-stone-100 font-medium shadow-sm'
                : 'text-stone-300 hover:bg-white/[0.04] border-l-4 border-transparent'"
            >
              <span class="truncate flex-1 mr-1.5">{{ truncateTitle(session.title) }}</span>
              <span
                @click="deleteSession(session.id, $event)"
                class="opacity-0 group-hover:opacity-100 flex-shrink-0 w-5 h-5 flex items-center justify-center rounded text-stone-400 hover:text-red-300 hover:bg-white/[0.06] transition-all cursor-pointer"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </span>
            </button>
          </template>
        </div>
      </div>

      <div class="border-t border-amber-100/10 p-3 space-y-2">
        <div class="text-[10px] uppercase tracking-wider text-stone-500 mb-1.5">{{ t('rightPanel.quickActions') }}</div>
        <div class="grid grid-cols-2 gap-1.5">
          <button
            @click="copyConversation"
            class="px-2 py-1.5 rounded-lg border border-amber-100/10 bg-white/[0.03] text-xs text-stone-300 hover:bg-white/[0.06] hover:border-amber-300/20 transition-colors flex items-center justify-center gap-1"
          >
            <span>📋</span>
            <span>{{ t('rightPanel.copy') }}</span>
          </button>
          <button
            @click="exportConversation"
            class="px-2 py-1.5 rounded-lg border border-amber-100/10 bg-white/[0.03] text-xs text-stone-300 hover:bg-white/[0.06] hover:border-amber-300/20 transition-colors flex items-center justify-center gap-1"
          >
            <span>📤</span>
            <span>{{ t('rightPanel.export') }}</span>
          </button>
          <button
            @click="router.push('/memory')"
            class="px-2 py-1.5 rounded-lg border border-amber-100/10 bg-white/[0.03] text-xs text-stone-300 hover:bg-white/[0.06] hover:border-amber-300/20 transition-colors flex items-center justify-center gap-1"
          >
            <span>🧠</span>
            <span>{{ t('rightPanel.memory') }}</span>
          </button>
          <button
            @click="clearConversation"
            class="px-2 py-1.5 rounded-lg border border-amber-100/10 bg-white/[0.03] text-xs text-stone-300 hover:bg-white/[0.06] hover:border-amber-300/20 transition-colors flex items-center justify-center gap-1"
          >
            <span>🗑️</span>
            <span>{{ t('rightPanel.clear') }}</span>
          </button>
        </div>
      </div>

      <div class="border-t border-amber-100/10 p-3">
        <div class="rounded-xl border border-amber-100/10 bg-white/[0.02] p-3 space-y-2">
          <div class="text-[10px] uppercase tracking-wider text-stone-500">{{ t('rightPanel.statusOverview') }}</div>
          <div class="space-y-1.5">
            <div class="flex items-center justify-between text-xs">
              <span class="text-stone-400">{{ t('rightPanel.sessionCount') }}</span>
              <span class="text-stone-200 font-medium">{{ sessionCount }}</span>
            </div>
            <div class="flex items-center justify-between text-xs">
              <span class="text-stone-400">{{ t('rightPanel.connectionStatus') }}</span>
              <span class="flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full" :class="wsStore.isConnected ? 'bg-emerald-400' : 'bg-rose-400'"></span>
                <span class="text-stone-200">{{ connectionStatus }}</span>
              </span>
            </div>
            <div class="flex items-center justify-between text-xs">
              <span class="text-stone-400">{{ t('rightPanel.unreadReminders') }}</span>
              <span class="text-stone-200 font-medium">{{ unreadCount }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="flex flex-1 flex-col items-center py-3">
        <button
          @click="newChat"
          class="flex-none shrink-0 p-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-stone-950 flex items-center justify-center"
          :title="t('chat.newChat')"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <span
          class="mt-3 inline-block text-[10px] text-stone-500 [writing-mode:vertical-rl] [text-orientation:upright]"
          :class="locale === 'en' ? 'uppercase tracking-[0.18em]' : 'tracking-[0.35em]'"
        >
          {{ t('chat.conversation') }}
        </span>
      </div>
    </template>
  </aside>
</template>
