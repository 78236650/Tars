<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { orchestrationApi } from '@/api'
import type { OrchestrationTask, OrchestrationTaskDetail, OrchestrationDispatchResult } from '@/types'
import BaseCard from '@/components/common/BaseCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import DispatchPanel from '@/components/orchestration/DispatchPanel.vue'
import AgentStatusCard from '@/components/orchestration/AgentStatusCard.vue'
import OrchestrationSharedSummary from '@/components/orchestration/OrchestrationSharedSummary.vue'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

const { t, locale } = useI18n()
const toast = useToast()

const tasks = ref<OrchestrationTask[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const drawerOpen = ref(false)
const detailLoading = ref(false)
const selectedDetail = ref<OrchestrationTaskDetail | null>(null)
const workflowStep = ref<1 | 2 | 3>(1)

const hasTasks = computed(() => tasks.value.length > 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / 20)))

const formatTime = (value: string | undefined) => {
  if (!value) return '—'
  return new Date(value).toLocaleString(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const statusClass = (status: string) => {
  switch (status) {
    case 'done':
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    case 'failed':
      return 'bg-red-500/15 text-red-300 border-red-500/30'
    default:
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  }
}

const statusLabel = (status: string) => {
  const key = `orchestration.status.${status}` as const
  const translated = t(key)
  return translated !== key ? translated : status
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await orchestrationApi.listTasks(page.value)
    tasks.value = res.tasks
    total.value = res.total
  } catch (e) {
    console.error(e)
    toast.error(t('orchestration.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function openDetail(taskId: string) {
  drawerOpen.value = true
  detailLoading.value = true
  selectedDetail.value = null
  workflowStep.value = 3
  try {
    selectedDetail.value = await orchestrationApi.getTask(taskId)
  } catch (e) {
    console.error(e)
    toast.error(t('orchestration.detailFailed'))
    drawerOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  selectedDetail.value = null
}

function prevPage() {
  if (page.value <= 1) return
  page.value -= 1
  void loadTasks()
}

function nextPage() {
  if (page.value >= totalPages.value) return
  page.value += 1
  void loadTasks()
}

async function onDispatched(result: OrchestrationDispatchResult) {
  await loadTasks()
  if (result.task_id) {
    await openDetail(result.task_id)
  }
}

function onStepChange(step: 1 | 2 | 3) {
  workflowStep.value = step
}

function startNew() {
  workflowStep.value = 1
  closeDrawer()
}

onMounted(() => {
  void loadTasks()
})

defineExpose({ openDetail, loadTasks })
</script>

<template>
  <div class="flex h-full flex-col gap-5 overflow-y-auto p-4 md:p-6 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-6 lg:overflow-hidden">
    <!-- 左侧：发起作业 -->
    <div class="min-h-0 space-y-4 lg:overflow-y-auto lg:pr-1">
      <DispatchPanel @dispatched="onDispatched" @step-change="onStepChange" />

      <div class="rounded-xl border border-border/60 bg-surface-2/50 p-4">
        <h3 class="mb-2 text-sm font-medium text-content">{{ t('orchestration.agentsTitle') }}</h3>
        <ul class="grid gap-2 sm:grid-cols-3">
          <li class="flex items-center gap-2 rounded-lg border border-sky-500/20 bg-sky-500/5 px-3 py-2 text-xs text-sky-100">
            <BaseIcon icon="lucide:anchor" :size="16" />
            {{ t('orchestration.agent.berth') }}
          </li>
          <li class="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-100">
            <BaseIcon icon="lucide:ship" :size="16" />
            {{ t('orchestration.agent.vessel') }}
          </li>
          <li class="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-100">
            <BaseIcon icon="lucide:warehouse" :size="16" />
            {{ t('orchestration.agent.yard') }}
          </li>
        </ul>
        <p class="mt-2 text-xs text-content-muted">{{ t('orchestration.agentsHint') }}</p>
      </div>
    </div>

    <!-- 右侧：历史记录 -->
    <div class="flex min-h-0 flex-col rounded-2xl border border-border bg-surface-2/60 lg:overflow-hidden">
      <header class="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 class="text-base font-semibold text-content">{{ t('orchestration.historyTitle') }}</h2>
          <p class="text-xs text-content-muted">{{ t('orchestration.historyHint') }}</p>
        </div>
        <button
          type="button"
          class="rounded-lg border border-border px-3 py-1.5 text-xs text-content hover:bg-surface-3"
          :disabled="loading"
          @click="loadTasks"
        >
          {{ t('common.refresh') }}
        </button>
      </header>

      <div class="min-h-0 flex-1 overflow-y-auto p-4">
        <div v-if="loading && !hasTasks" class="text-sm text-content-muted">
          {{ t('common.loading') }}
        </div>

        <EmptyState v-else-if="!hasTasks" :text="t('orchestration.emptyBiz')">
          <template #icon>
            <BaseIcon icon="lucide:clipboard-list" class="h-12 w-12 opacity-40" />
          </template>
        </EmptyState>

        <ul v-else class="space-y-3">
          <li v-for="task in tasks" :key="task.id">
            <button
              type="button"
              class="w-full rounded-xl border border-border bg-surface-1 p-4 text-left transition hover:border-accent/40 hover:bg-surface-2"
              @click="openDetail(task.id)"
            >
              <div class="flex items-start justify-between gap-2">
                <p class="font-medium text-content line-clamp-2">{{ task.goal }}</p>
                <span
                  class="shrink-0 rounded-full border px-2 py-0.5 text-xs"
                  :class="statusClass(task.status)"
                >
                  {{ statusLabel(task.status) }}
                </span>
              </div>
              <p class="mt-2 text-xs text-content-muted">{{ formatTime(task.created_at) }}</p>
            </button>
          </li>
        </ul>
      </div>

      <footer
        v-if="total > 20"
        class="flex shrink-0 items-center justify-center gap-3 border-t border-border py-3 text-sm text-content-muted"
      >
        <button
          type="button"
          class="rounded border border-border px-2 py-1 disabled:opacity-40"
          :disabled="page <= 1"
          @click="prevPage"
        >
          {{ t('orchestration.prevPage') }}
        </button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="rounded border border-border px-2 py-1 disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="nextPage"
        >
          {{ t('orchestration.nextPage') }}
        </button>
      </footer>
    </div>

    <Teleport to="body">
      <div
        v-if="drawerOpen"
        class="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
        @click.self="closeDrawer"
      >
        <aside
          class="flex h-full w-full max-w-xl flex-col border-l border-border bg-surface-1 shadow-2xl"
          role="dialog"
          :aria-label="t('orchestration.detailTitle')"
        >
          <header class="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 class="text-lg font-semibold text-content">{{ t('orchestration.detailTitle') }}</h2>
              <p class="text-xs text-content-muted">{{ t('orchestration.detailSubtitle') }}</p>
            </div>
            <div class="flex gap-2">
              <button
                type="button"
                class="rounded-lg border border-border px-3 py-1.5 text-xs text-content hover:bg-surface-2"
                @click="startNew"
              >
                {{ t('orchestration.newTask') }}
              </button>
              <button
                type="button"
                class="rounded-lg p-2 text-content-muted hover:bg-surface-2 hover:text-content"
                :aria-label="t('common.cancel')"
                @click="closeDrawer"
              >
                <BaseIcon icon="lucide:x" :size="20" />
              </button>
            </div>
          </header>

          <div v-if="detailLoading" class="p-6 text-sm text-content-muted">
            {{ t('common.loading') }}
          </div>

          <div v-else-if="selectedDetail" class="flex-1 space-y-5 overflow-y-auto p-5">
            <section class="rounded-xl border border-border bg-surface-2 p-4">
              <p class="text-xs font-medium uppercase tracking-wide text-content-muted">
                {{ t('orchestration.goal') }}
              </p>
              <p class="mt-2 text-base text-content">{{ selectedDetail.task.goal }}</p>
              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  class="rounded-full border px-2.5 py-0.5 text-xs"
                  :class="statusClass(selectedDetail.task.status)"
                >
                  {{ statusLabel(selectedDetail.task.status) }}
                </span>
                <span class="text-xs text-content-muted">{{
                  formatTime(selectedDetail.task.created_at)
                }}</span>
              </div>
            </section>

            <section v-if="Array.isArray(selectedDetail.shared.conflicts) && selectedDetail.shared.conflicts.length">
              <div class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
                <h3 class="mb-2 flex items-center gap-2 text-sm font-medium text-amber-200">
                  <BaseIcon icon="lucide:alert-triangle" :size="16" />
                  {{ t('orchestration.conflicts') }}
                </h3>
                <ul class="list-disc space-y-1 pl-4 text-sm text-amber-100">
                  <li v-for="(c, i) in selectedDetail.shared.conflicts as string[]" :key="i">{{ c }}</li>
                </ul>
              </div>
            </section>

            <section>
              <h3 class="mb-3 text-sm font-semibold text-content">{{ t('orchestration.expertResults') }}</h3>
              <EmptyState
                v-if="!selectedDetail.outputs.length"
                :text="t('orchestration.noOutputs')"
                class="py-6"
              />
              <div v-else class="space-y-3">
                <AgentStatusCard
                  v-for="(out, idx) in selectedDetail.outputs"
                  :key="idx"
                  :agent-type="out.agent_type"
                  :subtask="out.subtask"
                  :output="out.output"
                  :status="out.status"
                />
              </div>
            </section>

            <section v-if="Object.keys(selectedDetail.shared).length">
              <h3 class="mb-3 text-sm font-semibold text-content">{{ t('orchestration.sharedSummary') }}</h3>
              <OrchestrationSharedSummary :shared="selectedDetail.shared" />
            </section>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>
