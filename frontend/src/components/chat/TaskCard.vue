<script setup lang="ts">
// v2.6.1: 内嵌任务进度卡片 — 替换 TaskPanel 抽屉
import { ref } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'

const wsStore = useWsStore()
const { t } = useI18n()

interface TaskStep {
  id: number; step_order: number; description: string; tool: string
  status: string; result?: string; error?: string; retries: number
}

interface Task {
  id: string; title: string; goal: string
  status: string; current_step: number; total_steps: number
  steps: TaskStep[]
  artifacts?: string[]; output_summary?: string
}

const props = defineProps<{ task: Task }>()

const expanded = ref(true)

const statusIcon = (s: string): string => {
  const m: Record<string, string> = { pending: 'lucide:circle', running: 'lucide:circle-half', completed: 'lucide:check', failed: 'lucide:x', skipped: 'lucide:arrow-right', paused: 'lucide:pause', aborted: 'lucide:circle-slash' }
  return m[s] || 'lucide:help-circle'
}

const statusColor = (s: string): string => {
  const m: Record<string, string> = {
    pending: 'text-slate-500', running: 'text-blue-400', completed: 'text-green-400',
    failed: 'text-red-400', skipped: 'text-amber-400', paused: 'text-amber-400', aborted: 'text-red-500',
  }
  return m[s] || 'text-slate-400'
}

const taskStatusLabel = (s: string): string => {
  const m: Record<string, string> = {
    pending: t('taskCard.status.pending'),
    running: t('taskCard.status.running'),
    completed: t('taskCard.status.completed'),
    failed: t('taskCard.status.failed'),
    skipped: t('taskCard.status.skipped'),
    paused: t('taskCard.status.paused'),
    aborted: t('taskCard.status.aborted'),
  }
  return m[s] || s
}

const sendDecision = (decision: string) => {
  wsStore.send({ type: 'user_decision', task_id: props.task.id, decision })
}
</script>

<template>
  <div class="task-card bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
    <div class="px-4 py-3 border-b border-slate-700/60 flex items-center justify-between cursor-pointer" @click="expanded = !expanded">
      <div class="flex items-center gap-3 min-w-0">
        <span class="text-lg">{{ expanded ? '▼' : '▶' }}</span>
        <div class="min-w-0">
          <p class="text-sm font-medium text-white truncate">{{ task.title }}</p>
          <p class="text-xs text-slate-500 truncate">{{ task.goal }}</p>
        </div>
      </div>
      <span class="text-xs px-2 py-0.5 rounded-full flex-shrink-0 ml-2" :class="statusColor(task.status)">
        <BaseIcon :icon="statusIcon(task.status)" :size="12" /> {{ taskStatusLabel(task.status) }}
      </span>
    </div>

    <div v-if="expanded" class="px-4 pb-3">
      <!-- Progress bar -->
      <div class="my-3">
        <div class="flex justify-between text-xs text-slate-500 mb-1">
          <span>{{ t('taskCard.stepsProgress', { current: task.current_step, total: task.total_steps }) }}</span>
        </div>
        <div class="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div class="h-full bg-blue-500 rounded-full transition-all duration-300"
            :style="{ width: ((task.current_step / Math.max(task.total_steps, 1)) * 100) + '%' }" />
        </div>
      </div>

      <!-- Steps -->
      <div class="space-y-1">
        <div v-for="step in task.steps" :key="step.id" class="flex items-start gap-2 text-xs py-0.5">
          <BaseIcon :icon="statusIcon(step.status)" :size="12" :class="statusColor(step.status)" class="mt-0.5 flex-shrink-0" />
          <div class="flex-1 min-w-0">
            <span class="text-slate-300">{{ step.description }}</span>
            <span v-if="step.tool" class="text-slate-600 ml-1">({{ step.tool }})</span>
            <div v-if="step.error" class="text-red-400 mt-0.5">{{ step.error }}</div>
            <span v-if="step.retries > 0" class="text-amber-400 ml-1 text-[10px]">{{ t('taskCard.retryCount', { count: step.retries }) }}</span>
          </div>
        </div>
      </div>

      <!-- Artifacts -->
      <div v-if="task.artifacts?.length && task.status === 'completed'" class="mt-3 pt-3 border-t border-slate-700/50">
        <p class="text-xs text-slate-500 mb-1"><BaseIcon icon="lucide:package" :size="14" /> {{ t('taskCard.artifacts') }}</p>
        <div v-for="art in task.artifacts" :key="art" class="text-xs text-slate-400 font-mono truncate">{{ art }}</div>
      </div>

      <!-- Output summary -->
      <div v-if="task.output_summary && task.status === 'completed'" class="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded p-2">
        {{ task.output_summary }}
      </div>

      <!-- Actions -->
      <div v-if="task.status === 'running'" class="flex gap-2 mt-3 pt-2 border-t border-slate-700/50">
        <button @click="sendDecision('pause')" class="text-xs px-2 py-1 rounded bg-amber-600/20 text-amber-400 hover:bg-amber-600/30">{{ t('taskCard.pause') }}</button>
        <button @click="sendDecision('abort')" class="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30">{{ t('taskCard.abort') }}</button>
      </div>
      <div v-else-if="task.status === 'paused'" class="flex gap-2 mt-3 pt-2 border-t border-slate-700/50">
        <button @click="sendDecision('resume')" class="text-xs px-2 py-1 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30">{{ t('taskCard.resume') }}</button>
        <button @click="sendDecision('abort')" class="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30">{{ t('taskCard.abort') }}</button>
      </div>
      <div v-else-if="task.status === 'failed' || task.status === 'aborted'" class="flex gap-2 mt-3 pt-2 border-t border-slate-700/50">
        <button @click="sendDecision('retry')" class="text-xs px-2 py-1 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30">{{ t('taskCard.retry') }}</button>
      </div>
    </div>
  </div>
</template>
