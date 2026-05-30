<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { useI18n } from '@/i18n'

const props = defineProps<{
  plan: { goal: string }
  steps: { id: number; description: string; tool: string; status: string; output?: string; error?: string }[]
}>()
const { t } = useI18n()
const completedCount = computed(() => props.steps.filter((s) => s.status === 'completed').length)

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed': return 'lucide:check-circle'
    case 'running': return 'lucide:refresh-cw'
    case 'failed': return 'lucide:x-circle'
    case 'skipped': return 'lucide:skip-forward'
    default: return 'lucide:square'
  }
}

const statusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'text-green-400'
    case 'running': return 'text-blue-400 animate-pulse'
    case 'failed': return 'text-red-400'
    case 'skipped': return 'text-slate-500'
    default: return 'text-slate-400'
  }
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-3">
    <div class="flex items-center gap-2 mb-3 pb-2 border-b border-slate-700">
      <BaseIcon icon="lucide:clipboard" :size="18" />
      <h4 class="font-semibold text-white">{{ t('planCard.title', { goal: plan.goal }) }}</h4>
    </div>

    <div class="space-y-2">
      <div
        v-for="step in steps"
        :key="step.id"
        class="flex items-start gap-2 text-sm"
      >
        <BaseIcon :icon="statusIcon(step.status)" :size="14" :class="statusColor(step.status)" />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-slate-300">{{ step.id }}. {{ step.description }}</span>
            <span class="text-xs px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">{{ step.tool }}</span>
          </div>
          <div v-if="step.output && step.status === 'completed'" class="mt-1 text-xs text-slate-500 bg-slate-900 rounded px-2 py-1 max-h-20 overflow-auto">
            {{ step.output.slice(0, 200) }}
          </div>
          <div v-if="step.error && step.status === 'failed'" class="mt-1 text-xs text-red-400">
            {{ step.error }}
          </div>
        </div>
      </div>
    </div>

    <div class="mt-3 pt-2 border-t border-slate-700 text-xs text-slate-500">
      {{ t('planCard.progress', { completed: completedCount, total: steps.length }) }}
    </div>
  </div>
</template>
