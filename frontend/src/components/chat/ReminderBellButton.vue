<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
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
    <BaseIcon icon="lucide:bell" :size="20" />
    <span
      v-if="props.unreadCount > 0"
      class="absolute -right-1 -top-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold leading-none text-white ring-2 ring-[#13100d]"
    >
      {{ badgeText }}
    </span>
  </button>
</template>
