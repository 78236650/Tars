<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { agentMeta } from './orchestration-meta'
import { useI18n } from '@/i18n'

const props = defineProps<{
  agentType: string
  subtask: string
  output: string
  status?: string
}>()

const { t } = useI18n()
const meta = computed(() => agentMeta(props.agentType))
const label = computed(() => t(meta.value.labelKey))
</script>

<template>
  <article
    class="overflow-hidden rounded-xl border border-border bg-surface-1"
    :aria-label="label"
  >
    <header
      class="flex items-center gap-3 border-b border-border px-4 py-3"
      :class="meta.accentClass"
    >
      <span class="flex h-9 w-9 items-center justify-center rounded-lg bg-black/20">
        <BaseIcon :icon="meta.icon" :size="18" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="font-medium">{{ label }}</p>
        <p v-if="subtask" class="truncate text-xs opacity-80">{{ subtask }}</p>
      </div>
      <span
        v-if="status"
        class="shrink-0 rounded-full border border-current/30 px-2 py-0.5 text-xs"
      >
        {{ status === 'done' ? t('orchestration.outputDone') : status }}
      </span>
    </header>
    <div class="px-4 py-3">
      <p class="whitespace-pre-wrap text-sm leading-relaxed text-content">{{ output }}</p>
    </div>
  </article>
</template>
