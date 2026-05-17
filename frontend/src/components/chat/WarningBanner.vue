<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'

const wsStore = useWsStore()
const { t } = useI18n()
const visible = ref(false)
const warningType = ref<'warning' | 'permission_denied'>('warning')
const message = ref('')
let unsubscribe: (() => void) | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: any) {
      if (data.type === 'warning') {
        warningType.value = 'warning'
        message.value = data.message || ''
        visible.value = true
      } else if (data.type === 'error' && data.code === 'permission_denied') {
        warningType.value = 'permission_denied'
        message.value = data.message || t('chat.permissionDenied')
        visible.value = true
      }

      if (visible.value) {
        if (hideTimer) clearTimeout(hideTimer)
        hideTimer = setTimeout(() => {
          visible.value = false
        }, 6000)
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
    v-if="visible"
    class="flex items-center gap-2 px-4 py-2 mx-4 mb-2 rounded-lg border text-sm"
    :class="warningType === 'permission_denied'
      ? 'bg-rose-500/10 border-rose-400/30 text-rose-100'
      : 'bg-rose-500/10 border-rose-400/30 text-rose-100'"
  >
    <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
    </svg>
    <span>{{ message }}</span>
    <button
      @click="visible = false"
      class="ml-auto text-current opacity-50 hover:opacity-100 transition-opacity"
    >
      ✕
    </button>
  </div>
</template>
