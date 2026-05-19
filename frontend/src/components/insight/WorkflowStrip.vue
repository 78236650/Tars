<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from '@/i18n'
import { insightApi, type InsightWorkflowState } from '@/api'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'

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
  <div v-if="visible" class="workflow-strip">
    <div class="strip-head">
      <span class="strip-title">{{ t('insight.workflow.title') }}</span>
      <span class="strip-step">{{ stepLabel }}</span>
      <span v-if="workflow?.datasource_name" class="strip-ds">{{ workflow.datasource_name }}</span>
    </div>

    <div v-if="workflow?.session_state === 'no_source' && datasources?.length" class="strip-body">
      <p class="strip-hint">{{ t('insight.workflow.pickSourceHint') }}</p>
      <select
        class="strip-select"
        :value="datasourceId"
        @change="onPickDatasource(($event.target as HTMLSelectElement).value)"
      >
        <option value="">{{ t('insight.selectDatasource') }}</option>
        <option v-for="ds in datasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
      </select>
    </div>

    <div v-else-if="workflow?.datasource_state === 'needs_forge'" class="strip-body">
      <p class="strip-hint">{{ t('insight.workflow.needsForgeHint') }}</p>
      <div class="strip-actions">
        <button type="button" class="btn-primary" :disabled="forging" @click="startForge()">
          {{ forging ? t('bi.insightProfiling') : t('insight.workflow.startForge') }}
        </button>
        <button type="button" class="btn-secondary" :disabled="forging" @click="showContinueInput = !showContinueInput">
          {{ t('insight.workflow.forgeAndContinue') }}
        </button>
      </div>
      <div v-if="showContinueInput" class="continue-box">
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

    <div v-else-if="workflow?.datasource_state === 'forging'" class="strip-body">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
      </div>
      <p class="strip-hint">{{ progressMessage || t('bi.insightProfiling') }} ({{ progressPercent }}%)</p>
    </div>

    <div v-else-if="workflow?.datasource_state === 'forge_failed'" class="strip-body strip-error">
      <p class="strip-hint">{{ workflow.block_reason || t('insight.workflow.forgeFailed') }}</p>
      <button type="button" class="btn-primary" :disabled="forging" @click="startForge()">
        {{ t('insight.retry') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.workflow-strip {
  margin: 0 16px 8px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(251, 191, 36, 0.2);
  background: rgba(251, 191, 36, 0.06);
}
.strip-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.strip-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #fbbf24;
}
.strip-step {
  font-size: 13px;
  color: #e7e5e4;
}
.strip-ds {
  font-size: 12px;
  color: #a8a29e;
  margin-left: auto;
}
.strip-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.strip-hint {
  font-size: 13px;
  color: #d6d3d1;
  margin: 0;
}
.strip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.strip-select,
.continue-input {
  width: 100%;
  max-width: 360px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: #f5f5f4;
  font-size: 13px;
}
.continue-box {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.progress-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  transition: width 0.3s ease;
}
.strip-error .strip-hint {
  color: #fecaca;
}
.btn-primary {
  padding: 8px 14px;
  border-radius: 8px;
  background: #f59e0b;
  color: #1c1917;
  font-size: 13px;
  font-weight: 500;
}
.btn-primary:disabled {
  opacity: 0.5;
}
.btn-secondary {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: #e7e5e4;
  font-size: 13px;
}
</style>
