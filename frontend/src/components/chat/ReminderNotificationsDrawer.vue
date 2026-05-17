<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useReminderNotificationsStore } from '@/stores/reminderNotifications'
import type { ReminderNotification, ReminderSummaryLog } from '@/types'
import { useI18n } from '@/i18n'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const reminderNotificationsStore = useReminderNotificationsStore()
const { t, locale } = useI18n()
const {
  items,
  selectedId,
  selectedDetail,
  loadingList,
  loadingDetail,
  errorMessage,
  unreadCount,
} = storeToRefs(reminderNotificationsStore)

const hasSelection = computed(() => !!selectedDetail.value)

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return t('memory.none')
  return new Date(value).toLocaleString(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'delivered':
      return t('reminder.status.delivered')
    case 'broadcast':
      return t('reminder.status.broadcast')
    case 'failed':
      return t('reminder.status.failed')
    default:
      return status || t('reminder.status.unknown')
  }
}

const getStatusClass = (status: string) => {
  switch (status) {
    case 'delivered':
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
    case 'broadcast':
      return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
    case 'failed':
      return 'border-rose-500/30 bg-rose-500/10 text-rose-300'
    default:
      return 'border-slate-600 bg-slate-800 text-slate-300'
  }
}

const getStepLabel = (log: ReminderSummaryLog) => {
  const labels: Record<string, string> = {
    scheduler_matched: t('reminder.step.schedulerMatched'),
    runtime_executing: t('reminder.step.runtimeExecuting'),
    notification_recorded: t('reminder.step.notificationRecorded'),
    websocket_delivery_attempted: t('reminder.step.websocketDeliveryAttempted'),
    delivery_result: t('reminder.step.deliveryResult'),
  }
  return labels[log.step] || log.step
}

const getTargetSessionLabel = (notification: ReminderNotification) => {
  if (notification.session_id) return notification.session_id
  if (notification.delivery_status === 'broadcast') return t('reminder.target.broadcastFallback')
  return t('reminder.target.unspecified')
}

const selectNotification = async (notification: ReminderNotification) => {
  await reminderNotificationsStore.selectNotification(notification.id)
}
</script>

<template>
  <div v-if="props.open" class="fixed inset-0 z-40">
    <button class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="emit('close')" />

    <aside class="absolute right-0 top-0 flex h-full w-full max-w-5xl border-l border-slate-700 bg-slate-900 shadow-2xl">
      <section class="flex w-full max-w-sm flex-col border-r border-slate-800">
        <header class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h2 class="text-base font-semibold text-white">{{ t('reminder.drawerTitle') }}</h2>
            <p class="mt-1 text-xs text-slate-400">{{ t('reminder.unreadCount', { count: unreadCount }) }}</p>
          </div>
          <button class="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white" @click="emit('close')">
            <span class="sr-only">{{ t('reminder.close') }}</span>
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto p-3">
          <div v-if="loadingList" class="rounded-2xl border border-slate-800 bg-slate-800/70 px-4 py-6 text-sm text-slate-400">
            {{ t('reminder.loadingList') }}
          </div>
          <div v-else-if="errorMessage" class="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {{ errorMessage }}
          </div>
          <div v-else-if="items.length === 0" class="rounded-2xl border border-dashed border-slate-700 px-4 py-8 text-center text-sm text-slate-400">
            {{ t('reminder.empty') }}
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="notification in items"
              :key="notification.id"
              type="button"
              class="w-full rounded-2xl border px-4 py-3 text-left transition-colors"
              :class="selectedId === notification.id
                ? 'border-blue-500/40 bg-blue-500/10'
                : 'border-slate-800 bg-slate-800/70 hover:border-slate-700 hover:bg-slate-800'"
              @click="selectNotification(notification)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="truncate text-sm font-medium text-white">{{ notification.task_name }}</span>
                    <span
                      v-if="!notification.is_read"
                      class="inline-flex h-2.5 w-2.5 rounded-full bg-rose-500"
                    />
                  </div>
                  <p class="mt-1 max-h-10 overflow-hidden text-xs leading-5 text-slate-300">{{ notification.message }}</p>
                </div>
                <span class="rounded-full border px-2 py-0.5 text-[10px]" :class="getStatusClass(notification.delivery_status)">
                  {{ getStatusLabel(notification.delivery_status) }}
                </span>
              </div>
              <div class="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                <span>{{ formatDateTime(notification.triggered_at) }}</span>
                <span>{{ notification.session_id || 'broadcast' }}</span>
              </div>
            </button>
          </div>
        </div>
      </section>

      <section class="hidden min-w-0 flex-1 flex-col md:flex">
        <header class="border-b border-slate-800 px-6 py-4">
          <h3 class="text-base font-semibold text-white">{{ t('reminder.detailTitle') }}</h3>
          <p class="mt-1 text-xs text-slate-400">{{ t('reminder.detailDescription') }}</p>
        </header>

        <div class="flex-1 overflow-y-auto px-6 py-5">
          <div v-if="loadingDetail" class="rounded-2xl border border-slate-800 px-4 py-6 text-sm text-slate-400">
            {{ t('reminder.loadingDetail') }}
          </div>
          <div v-else-if="!hasSelection" class="rounded-2xl border border-dashed border-slate-700 px-4 py-8 text-center text-sm text-slate-400">
            {{ t('reminder.emptyDetail') }}
          </div>
          <div v-else-if="selectedDetail" class="space-y-5">
            <div class="rounded-3xl border border-slate-800 bg-slate-800/70 p-5">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Reminder</p>
                  <h4 class="mt-2 text-lg font-semibold text-white">{{ selectedDetail.task_name }}</h4>
                </div>
                <span class="rounded-full border px-3 py-1 text-xs" :class="getStatusClass(selectedDetail.delivery_status)">
                  {{ getStatusLabel(selectedDetail.delivery_status) }}
                </span>
              </div>

              <div class="mt-4 rounded-2xl bg-slate-900/70 p-4">
                <p class="text-xs text-slate-500">{{ t('reminder.contentLabel') }}</p>
                <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{{ selectedDetail.message }}</p>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-2">
                <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <p class="text-xs text-slate-500">{{ t('reminder.triggeredAt') }}</p>
                  <p class="mt-2 text-sm text-slate-200">{{ formatDateTime(selectedDetail.triggered_at) }}</p>
                </div>
                <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <p class="text-xs text-slate-500">{{ t('reminder.targetSession') }}</p>
                  <p class="mt-2 break-all text-sm text-slate-200">{{ getTargetSessionLabel(selectedDetail) }}</p>
                </div>
                <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <p class="text-xs text-slate-500">{{ t('reminder.readAt') }}</p>
                  <p class="mt-2 text-sm text-slate-200">{{ formatDateTime(selectedDetail.read_at) }}</p>
                </div>
                <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <p class="text-xs text-slate-500">{{ t('reminder.taskId') }}</p>
                  <p class="mt-2 break-all text-sm text-slate-200">{{ selectedDetail.job_id }}</p>
                </div>
              </div>

              <div
                v-if="selectedDetail.error_message"
                class="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
              >
                {{ selectedDetail.error_message }}
              </div>
            </div>

            <div class="rounded-3xl border border-slate-800 bg-slate-800/60 p-5">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <h4 class="text-sm font-semibold text-white">{{ t('reminder.summaryLogTitle') }}</h4>
                  <p class="mt-1 text-xs text-slate-500">{{ t('reminder.summaryLogDescription') }}</p>
                </div>
              </div>

              <div
                v-if="!selectedDetail.summary_logs || selectedDetail.summary_logs.length === 0"
                class="mt-4 rounded-2xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-400"
              >
                {{ t('reminder.emptySummaryLog') }}
              </div>
              <div v-else class="mt-4 space-y-3">
                <div
                  v-for="(log, index) in selectedDetail.summary_logs"
                  :key="`${log.step}-${index}`"
                  class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <div class="flex items-center gap-3">
                      <span class="flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-300">
                        {{ index + 1 }}
                      </span>
                      <div>
                        <p class="text-sm font-medium text-slate-100">{{ getStepLabel(log) }}</p>
                        <p class="mt-1 text-xs text-slate-500">{{ log.step }}</p>
                      </div>
                    </div>
                    <span class="rounded-full border px-2.5 py-1 text-[11px]" :class="getStatusClass(log.status)">
                      {{ getStatusLabel(log.status) }}
                    </span>
                  </div>
                  <p class="mt-3 text-sm leading-6 text-slate-300">{{ log.message }}</p>
                  <p v-if="log.timestamp" class="mt-2 text-[11px] text-slate-500">{{ formatDateTime(log.timestamp) }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </aside>
  </div>
</template>
