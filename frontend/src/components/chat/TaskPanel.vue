<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWsStore } from '@/stores/wsStore'

const wsStore = useWsStore()

interface TaskStep {
  id: number; step_order: number; description: string; tool: string;
  status: string; result?: string; error?: string; retries: number;
  started_at?: string; completed_at?: string;
}

interface Task {
  id: string; title: string; goal: string;
  workspace_path: string; workspace_source: string;
  status: string; current_step: number; total_steps: number;
  artifacts?: string[]; output_summary?: string;
  steps: TaskStep[];
}

const props = defineProps<{
  tasks: Task[]
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  pause: [taskId: string]
  resume: [taskId: string]
  cancel: [taskId: string]
  retry: [taskId: string]
}>()

const expandedTasks = ref<Set<string>>(new Set())

const toggleExpand = (taskId: string) => {
  if (expandedTasks.value.has(taskId)) {
    expandedTasks.value.delete(taskId)
  } else {
    expandedTasks.value.add(taskId)
    // tars_repo_root 首次展开时弹确认
    const task = props.tasks.find(t => t.id === taskId)
    if (task && task.workspace_source === 'tars_repo_root' && !sessionStorage.getItem('ws_confirmed_' + taskId)) {
      confirmNeeded.value = taskId
      sessionStorage.setItem('ws_confirmed_' + taskId, '1')
    }
  }
}

const statusIcon = (status: string): string => {
  const icons: Record<string, string> = { pending: '○', running: '◐', completed: '✓', failed: '✕', skipped: '→', paused: '⏸', aborted: '⊘' }
  return icons[status] || '?'
}

const statusColor = (status: string): string => {
  const colors: Record<string, string> = {
    pending: 'text-slate-500', running: 'text-blue-400 animate-pulse',
    completed: 'text-green-400', failed: 'text-red-400', skipped: 'text-amber-400',
    paused: 'text-amber-400', aborted: 'text-red-500',
  }
  return colors[status] || 'text-slate-400'
}

const wsSourceLabel = (source: string): string => {
  const labels: Record<string, string> = {
    api: '用户指定', workspace_manager: '当前项目', tars_repo_root: 'TARS仓库根', tars_fallback: '临时工作区',
  }
  return labels[source] || source
}

const wsSourceStyle = (source: string): string => {
  const styles: Record<string, string> = {
    api: 'bg-green-600/20 text-green-400', workspace_manager: 'bg-green-600/20 text-green-400',
    tars_repo_root: 'bg-amber-600/20 text-amber-400', tars_fallback: 'bg-blue-600/20 text-blue-400',
  }
  return styles[source] || 'bg-slate-700 text-slate-300'
}

const confirmNeeded = ref<string | null>(null)
const doConfirmWorkspace = () => { confirmNeeded.value = null }
const doRejectWorkspace = () => { confirmNeeded.value = null }

const dangerConfirm = ref<string | null>(null)
const dangerInput = ref('')
const doDangerConfirm = (taskId: string) => {
  if (dangerInput.value.trim().toLowerCase() === 'yes') {
    wsStore.send({ type: 'user_decision', task_id: taskId, decision: 'retry' })
    dangerConfirm.value = null
    dangerInput.value = ''
  }
}

const onPause = (taskId: string) => { emit('pause', taskId) }
const onResume = (taskId: string) => { emit('resume', taskId) }
const onCancel = (taskId: string) => { emit('cancel', taskId) }
const onRetry = (taskId: string) => { emit('retry', taskId) }

const truncate = (s: string, n: number) => s.length > n ? s.slice(0, n) + '...' : s

const runningTasks = computed(() => props.tasks.filter(t => t.status === 'running' || t.status === 'pending'))
</script>

<template>
  <Transition name="drawer">
    <div v-if="visible" class="task-panel flex flex-col h-full border-l border-slate-700 bg-slate-800/95">
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-white">任务</span>
          <span v-if="runningTasks.length" class="text-xs px-1.5 py-0.5 rounded-full bg-blue-600/30 text-blue-400">
            {{ runningTasks.length }} 进行中
          </span>
        </div>
        <button @click="$emit('close')" class="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="tasks.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 px-4">
        <svg class="w-10 h-10 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
        <p class="text-xs">暂无任务</p>
        <p class="text-xs mt-1 text-slate-600">输入 /plan 或包含"部署/构建/发布"等关键词触发</p>
      </div>

      <!-- Task list -->
      <div v-else class="flex-1 overflow-y-auto">
        <div v-for="task in tasks" :key="task.id" class="border-b border-slate-700/50">
          <!-- Task header -->
          <button @click="toggleExpand(task.id)" class="w-full px-4 py-3 text-left hover:bg-slate-700/30 transition-colors">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-medium text-white truncate flex-1 mr-2">{{ task.title }}</span>
              <span class="text-xs px-1.5 py-0.5 rounded" :class="statusColor(task.status)">
                {{ statusIcon(task.status) }} {{ task.status }}
              </span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <span class="text-slate-500">{{ task.goal }}</span>
            </div>
            <!-- Workspace badge -->
            <div class="mt-1 flex items-center gap-2">
              <span class="text-xs px-1.5 py-0.5 rounded-full" :class="wsSourceStyle(task.workspace_source)">
                {{ wsSourceLabel(task.workspace_source) }}
              </span>
              <span class="text-[10px] text-slate-600 truncate">{{ truncate(task.workspace_path, 40) }}</span>
            </div>
          </button>

          <!-- Expanded steps -->
          <div v-if="expandedTasks.has(task.id)" class="px-4 pb-3">
            <!-- Progress -->
            <div class="mb-3">
              <div class="flex items-center justify-between text-xs text-slate-500 mb-1">
                <span>步骤 {{ task.current_step }}/{{ task.total_steps }}</span>
              </div>
              <div class="w-full h-1 bg-slate-700 rounded-full overflow-hidden">
                <div class="h-full bg-blue-500 rounded-full transition-all" :style="{ width: ((task.current_step / Math.max(task.total_steps, 1)) * 100) + '%' }"></div>
              </div>
            </div>

            <!-- Steps -->
            <div class="space-y-1">
              <div v-for="step in task.steps" :key="step.id"
                class="flex items-start gap-2 text-xs py-1"
              >
                <span class="mt-0.5 flex-shrink-0" :class="statusColor(step.status)">{{ statusIcon(step.status) }}</span>
                <div class="flex-1 min-w-0">
                  <span class="text-slate-300">{{ step.description }}</span>
                  <span v-if="step.tool" class="text-slate-600 ml-1">({{ step.tool }})</span>
                  <div v-if="step.error" class="text-red-400 mt-0.5">{{ step.error }}</div>
                  <div v-if="step.result" class="text-slate-500 mt-0.5 truncate">{{ truncate(step.result, 80) }}</div>
                  <span v-if="step.retries > 0" class="text-amber-400 ml-1">重试{{ step.retries }}次</span>
                </div>
              </div>
            </div>

            <!-- Artifacts -->
            <div v-if="task.artifacts?.length && task.status === 'completed'" class="mt-3 pt-3 border-t border-slate-700/50">
              <p class="text-xs text-slate-500 mb-1">📦 产出文件</p>
              <div v-for="art in task.artifacts" :key="art" class="text-xs text-slate-400 font-mono">{{ art }}</div>
            </div>

            <!-- Output summary -->
            <div v-if="task.output_summary && task.status === 'completed'" class="mt-2 text-xs text-slate-400 bg-slate-900/50 rounded p-2">
              {{ task.output_summary }}
            </div>

            <!-- tars_repo_root 确认弹窗 -->
            <div v-if="confirmNeeded === task.id" class="mt-2 p-2 bg-amber-900/20 border border-amber-700/40 rounded text-xs">
              <p class="text-amber-300 mb-2">⚠️ 工作区指向 TARS 仓库根目录，非用户项目目录。确认继续？</p>
              <div class="flex gap-2">
                <button @click="doConfirmWorkspace" class="px-2 py-1 rounded bg-amber-600/30 text-amber-300 hover:bg-amber-600/50">确认</button>
                <button @click="doRejectWorkspace" class="px-2 py-1 rounded bg-slate-600/30 text-slate-400 hover:bg-slate-600/50">取消</button>
              </div>
            </div>
            <!-- confirmation_needed critical 输入框 -->
            <div v-if="dangerConfirm === task.id" class="mt-2 p-2 bg-red-900/20 border border-red-700/40 rounded text-xs">
              <p class="text-red-300 mb-2">⚠️ 危险命令，输入 "yes" 确认执行</p>
              <div class="flex gap-2">
                <input v-model="dangerInput" @keyup.enter="doDangerConfirm(task.id)" class="flex-1 px-2 py-1 bg-slate-900 border border-slate-600 rounded text-white text-xs" placeholder='输入 "yes"' />
                <button @click="doDangerConfirm(task.id)" class="px-3 py-1 rounded bg-red-600/30 text-red-300 hover:bg-red-600/50">确认</button>
                <button @click="dangerConfirm = null" class="px-3 py-1 rounded bg-slate-600/30 text-slate-400 hover:bg-slate-600/50">取消</button>
              </div>
            </div>
            <!-- Action buttons -->
            <div class="flex items-center gap-2 mt-3 pt-2 border-t border-slate-700/50">
              <template v-if="task.status === 'running'">
                <button @click="$emit('pause', task.id)" class="text-xs px-2 py-1 rounded bg-amber-600/20 text-amber-400 hover:bg-amber-600/30 transition-colors">暂停</button>
                <button @click="$emit('cancel', task.id)" class="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors">取消</button>
              </template>
              <template v-else-if="task.status === 'paused'">
                <button @click="$emit('resume', task.id)" class="text-xs px-2 py-1 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 transition-colors">恢复</button>
                <button @click="$emit('cancel', task.id)" class="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors">取消</button>
              </template>
              <template v-else-if="task.status === 'failed' || task.status === 'aborted'">
                <button @click="$emit('retry', task.id)" class="text-xs px-2 py-1 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 transition-colors">重试</button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.task-panel { width: 360px; }
.drawer-enter-active, .drawer-leave-active { transition: transform 0.25s ease, opacity 0.25s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(100%); opacity: 0.5; }

@media (max-width: 1199px) {
  .task-panel { position: fixed; right: 0; top: 0; bottom: 0; z-index: 40; width: 360px; box-shadow: -4px 0 20px rgba(0,0,0,0.4); }
}
@media (max-width: 899px) {
  .task-panel { position: fixed; right: 0; bottom: 0; left: 0; top: auto; height: 66vh; width: 100%; border-radius: 12px 12px 0 0; border-left: none; border-top: 1px solid #334155; }
}
</style>