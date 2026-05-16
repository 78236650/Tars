<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LeftPanel from '@/components/layout/LeftPanel.vue'
import RightPanel from '@/components/layout/RightPanel.vue'
import ReminderBellButton from '@/components/chat/ReminderBellButton.vue'
import ReminderNotificationsDrawer from '@/components/chat/ReminderNotificationsDrawer.vue'
import { useChatStore } from '@/stores/chat'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import { useSettingsStore } from '@/stores/settings'
import { useWsStore } from '@/stores/wsStore'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const chatStore = useChatStore()
const wsStore = useWsStore()
const reminderStore = useReminderNotificationsStore()

const desktopTitle = computed(() => String(route.meta.desktopTitle || 'TARS Workspace'))
const desktopSubtitle = computed(() => String(route.meta.desktopSubtitle || '统一桌面工作台'))

const openReminderNotifications = async () => {
  try {
    await reminderStore.openDrawer()
  } catch {}
}

const closeReminderNotifications = () => {
  reminderStore.closeDrawer()
}
</script>

<template>
  <div class="h-screen overflow-hidden bg-[#0c0b09] text-white">
    <div class="grid h-full grid-cols-[auto,1fr,auto]">
      <LeftPanel />

      <main
        class="flex min-w-0 flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(217,119,6,0.16),_transparent_34%),radial-gradient(circle_at_right,_rgba(120,53,15,0.18),_transparent_28%),linear-gradient(180deg,_rgba(23,20,17,0.98),_rgba(8,7,5,1))]"
      >
        <header class="flex shrink-0 items-center justify-between border-b border-amber-100/10 px-6 py-4 backdrop-blur-xl">
          <div class="min-w-0">
            <div class="flex items-center gap-3">
              <span class="rounded-full border border-amber-400/25 bg-amber-500/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.24em] text-amber-200">
                Graphite Amber
              </span>
              <span class="h-2 w-2 rounded-full" :class="wsStore.isConnected ? 'bg-emerald-400' : 'bg-rose-400'"></span>
            </div>
            <h1 class="mt-3 truncate text-2xl font-semibold tracking-tight text-stone-50">{{ desktopTitle }}</h1>
            <p class="mt-1 truncate text-sm text-stone-400">{{ desktopSubtitle }}</p>
          </div>

          <div class="flex items-center gap-3">
            <div class="hidden rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 lg:block">
              <div class="text-[11px] uppercase tracking-[0.22em] text-stone-500">Model</div>
              <div class="mt-1 text-sm font-medium text-stone-100">{{ settingsStore.currentModel || '未选择模型' }}</div>
            </div>
            <button
              type="button"
              class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 text-sm text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
              @click="router.push('/models')"
            >
              模型
            </button>
            <ReminderBellButton :unread-count="reminderStore.unreadCount" @open="openReminderNotifications" />
          </div>
        </header>

        <div class="min-h-0 flex-1 overflow-hidden p-4 lg:p-6">
          <div class="h-full min-h-0 rounded-[28px] border border-amber-100/10 bg-[#14110f]/88 shadow-[0_30px_120px_rgba(8,7,5,0.55)]">
            <slot />
          </div>
        </div>
      </main>

      <RightPanel />
    </div>

    <ReminderNotificationsDrawer :open="reminderStore.isDrawerOpen" @close="closeReminderNotifications" />
  </div>
</template>
