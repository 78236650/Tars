<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
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
    <BaseIcon icon="lucide:triangle-alert" :size="16" class="w-4 h-4 flex-shrink-0" />
    <span>{{ message }}</span>
    <button
      @click="visible = false"
      class="ml-auto text-current opacity-50 hover:opacity-100 transition-opacity"
    >
      <BaseIcon icon="lucide:x" :size="16" />
    </button>
  </div>
</template>
