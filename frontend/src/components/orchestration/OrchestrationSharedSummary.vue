<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { agentMeta, formatSharedSummary } from './orchestration-meta'
import { useI18n } from '@/i18n'

const props = defineProps<{
  shared: Record<string, unknown>
}>()

const { t } = useI18n()
const rows = computed(() => formatSharedSummary(props.shared))
const showRaw = computed(() => Object.keys(props.shared).filter((k) => k !== 'conflicts').length > 0)
</script>

<template>
  <div v-if="rows.length" class="space-y-2">
    <div
      v-for="row in rows"
      :key="row.key"
      class="flex gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2.5"
    >
      <BaseIcon :icon="agentMeta(row.key).icon" :size="18" class="mt-0.5 shrink-0 text-accent" />
      <div class="min-w-0">
        <p class="text-xs font-medium text-content-muted">{{ t(agentMeta(row.key).labelKey) }}</p>
        <p class="mt-0.5 text-sm text-content">{{ row.text }}</p>
      </div>
    </div>
  </div>
  <details v-if="showRaw" class="group rounded-lg border border-border bg-surface-2">
    <summary class="cursor-pointer px-3 py-2 text-xs text-content-muted hover:text-content">
      {{ t('orchestration.sharedRaw') }}
    </summary>
    <pre class="max-h-40 overflow-auto border-t border-border px-3 py-2 text-xs text-content-muted">{{
      JSON.stringify(shared, null, 2)
    }}</pre>
  </details>
</template>
