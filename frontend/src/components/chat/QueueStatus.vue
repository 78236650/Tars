<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'

const wsStore = useWsStore()
const { t } = useI18n()
const isQueued = ref(false)
const queueMessage = ref('')
let unsubscribe: (() => void) | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: any) {
      if (data.type === 'error' && data.code === 'rate_limited') {
        isQueued.value = true
        queueMessage.value = data.message || ''
        if (hideTimer) clearTimeout(hideTimer)
        hideTimer = setTimeout(() => {
          isQueued.value = false
        }, 5000)
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
    <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.3" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
    <span>{{ queueMessage || t('chat.rateLimited') }}</span>
  </div>
</template>
