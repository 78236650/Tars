<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from '@/i18n'
import { insightApi, type InsightWorkflowState } from '@/api'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'
import BaseIcon from '@/components/common/BaseIcon.vue'

const props = defineProps<{
  datasourceId: string
  sessionId?: string
  datasources?: { id: string; name: string }[]
}>()

const emit = defineEmits<{
  'update:datasourceId': [id: string]
  forged: []
}>()

const { t } = useI18n()
const toast = useToast()

const workflow = ref<InsightWorkflowState | null>(null)
const loading = ref(false)
const forging = ref(false)
const continueQuestion = ref('')
const showContinueInput = ref(false)
const collapsed = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

const visible = computed(() => Boolean(workflow.value?.show_workflow_strip))

const stepLabel = computed(() => {
  const ds = workflow.value?.datasource_state
  const ss = workflow.value?.session_state
  if (ss === 'no_source') return t('insight.workflow.stepPickSource')
  if (ds === 'needs_forge') return t('insight.workflow.stepForge')
  if (ds === 'forging') return t('insight.workflow.stepKnow')
  if (ds === 'forge_failed') return t('insight.workflow.stepForgeFailed')
  return t('insight.workflow.stepForge')
})

const progressPercent = computed(() => workflow.value?.forge_progress?.percent ?? 0)
const progressMessage = computed(() => workflow.value?.forge_progress?.message || '')

const hintText = computed(() => {
  const w = workflow.value
  if (!w) return ''
  if (w.session_state === 'no_source') return t('insight.workflow.pickSourceHint')
  if (w.datasource_state === 'needs_forge') return t('insight.workflow.needsForgeHint')
  if (w.datasource_state === 'forging') {
    return progressMessage.value
      ? `${progressMessage.value} (${progressPercent.value}%)`
      : `${t('bi.insightProfiling')} (${progressPercent.value}%)`
  }
  if (w.datasource_state === 'forge_failed') {
    return w.block_reason || t('insight.workflow.forgeFailed')
  }
  return ''
})

async function refreshWorkflow() {
  if (!props.datasourceId) return
  try {
    workflow.value = (await insightApi.getWorkflow(
      props.datasourceId,
      props.sessionId
    )) as InsightWorkflowState
  } catch {
    workflow.value = null
  }
}

async function startForge(pendingQuestion?: string) {
  if (!props.datasourceId || forging.value) return
  forging.value = true
  try {
    await insightApi.startForge(props.datasourceId, {
      force: true,
      pending_question: pendingQuestion,
      session_id: props.sessionId,
    })
    showContinueInput.value = false
    continueQuestion.value = ''
    await refreshWorkflow()
    emit('forged')
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('insight.workflow.forgeFailed')))
  } finally {
    forging.value = false
  }
}

function onPickDatasource(id: string) {
  emit('update:datasourceId', id)
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (visible.value || workflow.value?.datasource_state === 'forging') {
      void refreshWorkflow()
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  loading.value = true
  await refreshWorkflow()
  loading.value = false
  startPolling()
})

onBeforeUnmount(stopPolling)

watch(
  () => [props.datasourceId, props.sessionId],
  async () => {
    await refreshWorkflow()
  }
)

watch(
  () => workflow.value?.datasource_state,
  (st) => {
    if (st === 'ready') emit('forged')
  }
)
</script>

<template>
  <div v-if="visible" class="workflow-strip" :class="{ 'is-collapsed': collapsed }">
    <div class="strip-row">
      <div class="strip-meta" :title="hintText">
        <span class="strip-badge">{{ t('insight.workflow.title') }}</span>
        <span class="strip-step">{{ stepLabel }}</span>
        <span v-if="workflow?.datasource_name" class="strip-ds">{{ workflow.datasource_name }}</span>
        <span v-if="collapsed && workflow?.datasource_state === 'forging'" class="strip-pct">
          {{ progressPercent }}%
        </span>
      </div>

      <button
        type="button"
        class="strip-toggle"
        :aria-expanded="!collapsed"
        :title="collapsed ? t('insight.workflow.expand') : t('insight.workflow.collapse')"
        @click="collapsed = !collapsed"
      >
        <BaseIcon class="strip-toggle-icon" icon="lucide:chevron-down" :size="16" />
      </button>

      <div v-if="!collapsed" class="strip-main">
        <template v-if="workflow?.session_state === 'no_source' && datasources?.length">
          <select
            class="strip-select"
            :value="datasourceId"
            :title="t('insight.workflow.pickSourceHint')"
            @change="onPickDatasource(($event.target as HTMLSelectElement).value)"
          >
            <option value="">{{ t('insight.selectDatasource') }}</option>
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
          </select>
        </template>

        <template v-else-if="workflow?.datasource_state === 'needs_forge'">
          <div class="strip-actions">
            <button
              type="button"
              class="btn-primary"
              :title="t('insight.workflow.needsForgeHint')"
              :disabled="forging"
              @click="startForge()"
            >
              {{ forging ? t('bi.insightProfiling') : t('insight.workflow.startForge') }}
            </button>
            <button
              type="button"
              class="btn-ghost"
              :disabled="forging"
              @click="showContinueInput = !showContinueInput"
            >
              {{ t('insight.workflow.forgeAndContinue') }}
            </button>
          </div>
        </template>

        <template v-else-if="workflow?.datasource_state === 'forging'">
          <div class="strip-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
            </div>
            <span class="strip-pct">{{ progressPercent }}%</span>
          </div>
        </template>

        <template v-else-if="workflow?.datasource_state === 'forge_failed'">
          <button
            type="button"
            class="btn-primary"
            :title="workflow.block_reason || t('insight.workflow.forgeFailed')"
            :disabled="forging"
            @click="startForge()"
          >
            {{ t('insight.retry') }}
          </button>
        </template>
      </div>
    </div>

    <div
      v-if="!collapsed && workflow?.datasource_state === 'needs_forge' && showContinueInput"
      class="strip-row strip-row--secondary"
    >
      <input
        v-model="continueQuestion"
        type="text"
        class="continue-input"
        :placeholder="t('insight.workflow.continuePlaceholder')"
      />
      <button
        type="button"
        class="btn-primary"
        :disabled="forging || !continueQuestion.trim()"
        @click="startForge(continueQuestion.trim())"
      >
        {{ t('insight.workflow.forgeAndContinue') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.workflow-strip {
  margin: 0 12px 4px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(251, 191, 36, 0.18);
  background: rgba(251, 191, 36, 0.05);
}
.strip-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
}
.strip-row--secondary {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.strip-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.strip-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #fbbf24;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(251, 191, 36, 0.12);
}
.strip-step {
  font-size: 12px;
  color: #e7e5e4;
  white-space: nowrap;
}
.strip-ds {
  font-size: 11px;
  color: #a8a29e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}
.strip-pct {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: #fbbf24;
}
.strip-toggle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}
.strip-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e7e5e4;
}
.strip-toggle-icon {
  transition: transform 0.15s ease;
}
.is-collapsed .strip-toggle-icon {
  transform: rotate(-90deg);
}
.strip-main {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.strip-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.strip-select,
.continue-input {
  min-width: 0;
  flex: 1;
  max-width: 200px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
  color: #f5f5f4;
  font-size: 12px;
  height: 28px;
}
.continue-input {
  max-width: none;
}
.strip-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 120px;
}
.progress-bar {
  flex: 1;
  width: 80px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  transition: width 0.3s ease;
}
.btn-primary {
  padding: 4px 10px;
  height: 28px;
  border-radius: 6px;
  background: #f59e0b;
  color: #1c1917;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.btn-primary:disabled {
  opacity: 0.5;
}
.btn-ghost {
  padding: 4px 8px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: transparent;
  color: #d6d3d1;
  font-size: 11px;
  white-space: nowrap;
}
.btn-ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
}
.is-collapsed {
  padding: 4px 8px;
}
.is-collapsed .strip-row {
  min-height: 24px;
}
@media (max-width: 640px) {
  .strip-main {
    width: 100%;
    justify-content: flex-start;
  }
  .strip-row {
    flex-wrap: wrap;
  }
}
</style>
