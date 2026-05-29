<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LeftPanel from '@/components/layout/LeftPanel.vue'
import RightPanel from '@/components/layout/RightPanel.vue'
import ReminderNotificationsDrawer from '@/components/chat/ReminderNotificationsDrawer.vue'
import { useI18n } from '@/i18n'
import { useChatStore } from '@/stores/chat'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'

const route = useRoute()
const chatStore = useChatStore()
const reminderStore = useReminderNotificationsStore()
const { t } = useI18n()

onMounted(() => {
  chatStore.initChatRealtime()
})

const desktopTitle = computed(() => {
  if (route.meta.desktopTitleKey) {
    return t(String(route.meta.desktopTitleKey))
  }

  if (route.meta.desktopTitle) {
    return String(route.meta.desktopTitle)
  }

  return t('desktop.default.title')
})

const desktopSubtitle = computed(() => {
  if (route.meta.desktopSubtitleKey) {
    return t(String(route.meta.desktopSubtitleKey))
  }

  if (route.meta.desktopSubtitle) {
    return String(route.meta.desktopSubtitle)
  }

  return t('desktop.default.subtitle')
})

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
  <div class="h-screen overflow-hidden bg-surface-0 text-white">
    <div class="grid h-full grid-cols-[auto,1fr,auto]">
      <LeftPanel />

      <main
        class="flex min-w-0 flex-col overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(217,119,6,0.16),_transparent_34%),radial-gradient(circle_at_right,_rgba(120,53,15,0.18),_transparent_28%),linear-gradient(180deg,_rgba(23,20,17,0.98),_rgba(8,7,5,1))]"
      >
        <header class="flex shrink-0 items-center border-b border-amber-100/10 px-6 py-4 backdrop-blur-xl">
          <div class="min-w-0">
            <h1 class="truncate text-2xl font-semibold tracking-tight text-stone-50">{{ desktopTitle }}</h1>
            <p class="mt-1 truncate text-sm text-stone-400">{{ desktopSubtitle }}</p>
          </div>
        </header>

        <div class="min-h-0 flex-1 overflow-hidden p-4 lg:p-6">
          <div class="h-full min-h-0 rounded-[28px] border border-amber-100/10 bg-surface-1/88 shadow-[0_30px_120px_rgba(8,7,5,0.55)]">
            <slot />
          </div>
        </div>
      </main>

      <RightPanel />
    </div>

    <ReminderNotificationsDrawer :open="reminderStore.isDrawerOpen" @close="closeReminderNotifications" />
  </div>
</template>
