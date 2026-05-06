<script setup lang="ts">
defineProps<{
  plan: { goal: string }
  steps: { id: number; description: string; tool: string; status: string; output?: string; error?: string }[]
}>()

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed': return '✅'
    case 'running': return '🔄'
    case 'failed': return '❌'
    case 'skipped': return '⏭️'
    default: return '⬜'
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
      <span class="text-lg">📋</span>
      <h4 class="font-semibold text-white">执行计划: {{ plan.goal }}</h4>
    </div>

    <div class="space-y-2">
      <div
        v-for="step in steps"
        :key="step.id"
        class="flex items-start gap-2 text-sm"
      >
        <span :class="statusColor(step.status)">{{ statusIcon(step.status) }}</span>
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
      进度: {{ steps.filter(s => s.status === 'completed').length }}/{{ steps.length }} 完成
    </div>
  </div>
</template>
