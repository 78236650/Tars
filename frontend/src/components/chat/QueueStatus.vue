<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'

const wsStore = useWsStore()
const { t } = useI18n()
const isQueued = ref(false)
const queueMessage = ref('')
const pendingCount = ref(0)
let unsubscribe: (() => void) | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

function showQueued(message?: string, pending?: number) {
  isQueued.value = true
  if (message) queueMessage.value = message
  if (typeof pending === 'number') pendingCount.value = pending
  if (hideTimer) clearTimeout(hideTimer)
  hideTimer = setTimeout(() => {
    isQueued.value = false
    pendingCount.value = 0
  }, 5000)
}

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: any) {
      if (data.type === 'queue_status') {
        const pending = Number(data.pending ?? 0)
        if (pending > 0) {
          showQueued(undefined, pending)
        } else {
          isQueued.value = false
          pendingCount.value = 0
          if (hideTimer) clearTimeout(hideTimer)
        }
        return
      }
      if (data.type === 'error' && data.code === 'rate_limited') {
        showQueued(data.message || '')
      }
    }
  })
})

onUnmounted(() => {
  if (unsubscribe) unsubscribe()
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<template>
  <div
    v-if="isQueued"
    class="flex items-center gap-2 px-4 py-2 mx-4 mb-2 rounded-lg bg-amber-500/10 border border-amber-300/20 text-amber-100 text-sm"
  >
    <BaseIcon icon="lucide:loader-circle" :size="20" class="animate-spin" />
    <span>{{
      queueMessage ||
      (pendingCount > 0
        ? t('chat.followUpQueued', { count: pendingCount })
        : t('chat.rateLimited'))
    }}</span>
  </div>
</template>
