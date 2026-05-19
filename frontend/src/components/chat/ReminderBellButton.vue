<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'

const props = defineProps<{
  unreadCount: number
}>()

const emit = defineEmits<{
  open: []
}>()

const { t } = useI18n()
const badgeText = computed(() => (props.unreadCount > 99 ? '99+' : String(props.unreadCount)))
</script>

<template>
  <button
    type="button"
        class="relative flex w-full items-center justify-center rounded-lg p-2 text-stone-400 transition-colors hover:bg-white/[0.04] hover:text-stone-100"
    :title="t('reminder.buttonTitle')"
    :aria-label="t('reminder.buttonOpen')"
    @click="emit('open')"
  >
    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="1.8"
        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V4a2 2 0 10-4 0v1.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
      />
    </svg>
    <span
      v-if="props.unreadCount > 0"
      class="absolute -right-1 -top-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold leading-none text-white ring-2 ring-[#13100d]"
    >
      {{ badgeText }}
    </span>
  </button>
</template>
