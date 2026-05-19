<template>
  <div class="insight-view">
    <header class="insight-header">
      <div>
        <h1>{{ t('insight.title') }}</h1>
        <p class="subtitle">{{ t('insight.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <select v-model="selectedId" class="ds-select" @change="loadBrief">
          <option value="">{{ t('insight.selectDatasource') }}</option>
          <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
            {{ ds.name }} ({{ ds.db_type }})
          </option>
        </select>
        <button class="btn-secondary" :disabled="!selectedId || loading" @click="loadBrief">
          {{ t('insight.refresh') }}
        </button>
        <button class="btn-secondary" :disabled="!selectedId" @click="goBi">
          {{ t('insight.openBi') }}
        </button>
      </div>
    </header>

    <div
      v-if="selectedId && (profiling || brief)"
      class="profile-status-bar"
      :class="statusBarClass"
    >
      <span class="status-bar-label">{{ t('insight.profileStatus') }}</span>
      <span class="status-bar-value">{{ statusBarText }}</span>
      <button
        v-if="!profiling"
        type="button"
        class="btn-inline status-bar-refresh"
        :disabled="loading"
        @click="loadBrief"
      >
        {{ t('insight.refresh') }}
      </button>
    </div>

    <div class="insight-body">
      <details v-if="!pageLoading" class="llm-panel panel" :open="llmPanelOpen">
        <summary class="llm-panel-summary">
          <span>{{ t('insight.llmTitle') }}</span>
          <span class="llm-summary-meta muted">{{ effectiveLabel }}</span>
        </summary>
        <p class="muted llm-hint">{{ t('insight.llmHint') }}</p>
        <label class="llm-radio">
          <input v-model="llmForm.use_chat_default" type="radio" :value="true" />
          {{ t('insight.llmUseChat') }}
          <span v-if="chatCurrentLabel" class="chat-current">（{{ chatCurrentLabel }}）</span>
        </label>
        <label class="llm-radio">
          <input v-model="llmForm.use_chat_default" type="radio" :value="false" />
          {{ t('insight.llmCustom') }}
        </label>
        <div v-if="!llmForm.use_chat_default" class="llm-custom">
          <div class="llm-row">
            <label>{{ t('insight.llmProvider') }}</label>
            <select v-model="llmForm.provider" class="ds-select" @change="onProviderChange">
              <option value="ollama">Ollama</option>
              <option value="openai_compatible">{{ t('insight.llmRemote') }}</option>
            </select>
          </div>
          <div v-if="llmForm.provider === 'openai_compatible'" class="llm-row">
            <label>{{ t('insight.llmEndpoint') }}</label>
            <select v-model="llmForm.endpoint_id" class="ds-select" @change="onEndpointChange">
              <option value="">{{ t('insight.llmPickEndpoint') }}</option>
              <option v-for="ep in endpoints" :key="ep.id" :value="ep.id">{{ ep.name }}</option>
            </select>
          </div>
          <div class="llm-row">
            <label>{{ t('insight.llmModel') }}</label>
            <select v-model="llmForm.model" class="ds-select">
              <option value="">{{ t('insight.llmPickModel') }}</option>
              <option v-for="m in modelChoices" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
        </div>
        <div class="llm-effective">{{ t('insight.llmEffective') }}：<strong>{{ effectiveLabel }}</strong></div>
        <div class="llm-actions">
          <button class="btn-secondary" :disabled="llmSaving || profiling" @click="saveLlmSettings">
            {{ llmSaving ? t('insight.llmSaving') : t('insight.llmSave') }}
          </button>
          <button class="btn-primary" :disabled="!selectedId || profiling" @click="runProfile">
            {{ profiling ? t('bi.insightProfiling') : t('insight.runProfile') }}
          </button>
        </div>
      </details>

      <div v-if="loadError" class="banner banner-error">
        {{ loadError }}
        <button class="btn-inline" @click="loadBrief">{{ t('insight.retry') }}</button>
      </div>

      <div v-if="pageLoading" class="empty-state">{{ t('insight.loading') }}</div>

      <div v-else-if="!datasources.length" class="empty-state">
        {{ t('insight.noDatasources') }}
        <button class="btn-primary" @click="goBi">{{ t('insight.openBi') }}</button>
      </div>

      <div v-else-if="!selectedId" class="empty-state">
        {{ t('insight.pickDatasource') }}
      </div>

      <template v-else-if="brief">
        <div class="banner banner-info">{{ t('insight.phaseHint') }}</div>

        <section class="cards">
          <div class="stat-card">
            <div class="stat-label">{{ t('insight.profileStatus') }}</div>
            <div class="stat-value" :class="brief.latest_run?.status">
              {{ runStatusLabel }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">{{ t('insight.tables') }}</div>
            <div class="stat-value">{{ brief.datasource.table_count }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">{{ t('insight.annotations') }}</div>
            <div class="stat-value">{{ brief.datasource.annotation_count }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">{{ t('insight.metrics') }}</div>
            <div class="stat-value">{{ brief.metrics.length }}</div>
          </div>
        </section>

        <section v-if="brief.latest_run?.error" class="panel panel-warn">
          <h2>{{ t('insight.lastRunError') }}</h2>
          <p class="muted">{{ brief.latest_run.error }}</p>
        </section>

        <section v-if="brief.llm_errors?.length" class="panel panel-warn">
          <h2>{{ t('insight.llmErrors') }}</h2>
          <p class="muted">{{ t('insight.llmErrorsHint') }}</p>
          <ul class="list">
            <li v-for="(err, i) in brief.llm_errors" :key="'llm-' + i">{{ err }}</li>
          </ul>
        </section>

        <section v-if="brief.open_questions?.length" class="panel">
          <h2>{{ t('insight.openQuestions') }}</h2>
          <ul class="list">
            <li v-for="(q, i) in brief.open_questions" :key="i">{{ q }}</li>
          </ul>
        </section>

        <section class="panel">
          <h2>{{ t('insight.relations') }}</h2>
          <div v-if="relations.length === 0" class="muted">{{ t('insight.noRelations') }}</div>
          <ul v-else class="list">
            <li v-for="(rel, i) in relations" :key="i">
              <code>{{ rel.from_ref }}</code> → <code>{{ rel.to_ref }}</code>
              <span v-if="rel.confidence" class="muted">({{ rel.confidence }})</span>
            </li>
          </ul>
        </section>

        <section class="panel">
          <h2>{{ t('insight.tableAnnotations') }}</h2>
          <div v-if="annotationTables.length === 0" class="muted">{{ t('insight.noAnnotations') }}</div>
          <div v-else class="table-grid">
            <div v-for="name in annotationTables" :key="name" class="table-card">
              <div class="table-name">{{ name }}</div>
              <div class="table-desc">{{ tableDescription(name) }}</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>{{ t('insight.chatGuide') }}</h2>
          <p class="muted">{{ t('insight.chatGuideBody') }}</p>
          <ul class="examples">
            <li v-for="ex in examples" :key="ex">{{ ex }}</li>
          </ul>
          <button class="btn-primary" @click="goChat">{{ t('insight.goChat') }}</button>
        </section>
      </template>

      <div v-else class="empty-state">
        {{ t('insight.loadFailed') }}
        <button class="btn-primary" @click="loadBrief">{{ t('insight.retry') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  biApi,
  insightApi,
  type InsightDatasourceBrief,
  type InsightLlmSettingsPayload,
  type InsightProfileRunSummary,
} from '@/api'
import type { DataSource, Endpoint } from '@/types'
import { useI18n } from '@/i18n'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const datasources = ref<DataSource[]>([])
const selectedId = ref('')
const brief = ref<InsightDatasourceBrief | null>(null)
const pageLoading = ref(true)
const loading = ref(false)
const loadError = ref('')
const profiling = ref(false)
const profilingMessage = ref('')
const llmPanelOpen = ref(true)
const llmSaving = ref(false)
const ollamaModels = ref<string[]>([])
const endpoints = ref<Endpoint[]>([])
const chatCurrentLabel = ref('')
const effectiveLabel = ref('')
const llmForm = ref<InsightLlmSettingsPayload>({
  use_chat_default: true,
  provider: 'ollama',
  model: '',
  endpoint_id: null,
})

const modelChoices = computed(() => {
  if (llmForm.value.provider === 'openai_compatible') {
    const ep = endpoints.value.find((e) => e.id === llmForm.value.endpoint_id)
    return ep?.models || []
  }
  return ollamaModels.value
})

const examples = [
  '鉴数Demo 已支付订单的 GMV 是多少？',
  'orders 和 order_items 怎么关联？',
  '哪些表是事实表？',
]

const runStatusLabel = computed(() => {
  const st = brief.value?.latest_run?.status
  if (!st) return t('insight.noRun')
  const key = `bi.insightStatus.${st}`
  const translated = t(key)
  return translated === key ? st : translated
})

const statusBarText = computed(() => {
  if (profiling.value && profilingMessage.value) return profilingMessage.value
  if (profiling.value) return t('bi.insightProfiling')
  return runStatusLabel.value
})

const statusBarClass = computed(() => {
  if (profiling.value) return 'is-running'
  const st = brief.value?.latest_run?.status
  if (st === 'completed') return 'is-ok'
  if (st === 'failed') return 'is-fail'
  return ''
})

watch(profiling, (running) => {
  if (running) llmPanelOpen.value = false
})

watch(
  () => brief.value?.latest_run?.status,
  (st) => {
    if (st === 'completed' || st === 'failed') llmPanelOpen.value = false
  }
)

const relations = computed(() => {
  const snap = brief.value?.insight_snapshot as { relations?: Array<Record<string, unknown>> } | undefined
  return (snap?.relations || []) as Array<{ from_ref?: string; to_ref?: string; confidence?: number }>
})

const annotationTables = computed(() => Object.keys(brief.value?.schema_annotations || {}))

function tableDescription(name: string): string {
  const ann = (brief.value?.schema_annotations || {})[name] as { description?: string; business_name?: string } | undefined
  return ann?.description || ann?.business_name || '—'
}

function pickBestRun(runs: InsightProfileRunSummary[]): InsightProfileRunSummary | undefined {
  return runs.find((r) => r.status === 'completed') || runs[0]
}

async function buildBrief(datasourceId: string): Promise<InsightDatasourceBrief> {
  const [ds, runsRes] = await Promise.all([
    biApi.getDataSource(datasourceId),
    insightApi.listProfileRuns(datasourceId),
  ])
  const latest = pickBestRun(runsRes.runs || [])
  let snapshot: Record<string, unknown> = {}
  if (latest?.id) {
    const run = await insightApi.getProfileRun(latest.id)
    snapshot = (run.insight_snapshot as Record<string, unknown>) || {}
  }
  const tables = ds.schema_snapshot?.tables || {}
  const annotations = ds.schema_annotations || {}
  return {
    datasource: {
      id: ds.id,
      name: ds.name,
      db_type: ds.db_type,
      table_count: Object.keys(tables).length,
      annotation_count: Object.keys(annotations).length,
    },
    latest_run: latest || null,
    insight_snapshot: snapshot,
    schema_annotations: annotations,
    metrics: [],
    open_questions: (snapshot.open_questions as string[]) || [],
    llm_errors: (snapshot.llm_errors as string[]) || [],
    llm_status: (snapshot.llm_status as string) || '',
    llm_used: snapshot.llm_used as Record<string, unknown> | undefined,
    phase: { profile: true, metric_qa_in_chat: false, workbench: true },
  }
}

async function waitForProfileRun(runId: string, maxWaitMs = 600_000): Promise<void> {
  const deadline = Date.now() + maxWaitMs
  while (Date.now() < deadline) {
    const run = await insightApi.getProfileRun(runId)
    const progress = run.progress as { message?: string; phase?: string } | undefined
    const msg = progress?.message || run.status || ''
    profilingMessage.value = t('insight.profilingProgress', { message: msg })
    if (run.status === 'completed' || run.status === 'failed') {
      return
    }
    await new Promise((r) => setTimeout(r, 2000))
  }
}

async function loadDatasources() {
  pageLoading.value = true
  loadError.value = ''
  try {
    const res = await biApi.listDataSources()
    datasources.value = res.datasources
    const fromQuery = String(route.query.datasource_id || '').trim()
    if (fromQuery && datasources.value.some((d) => d.id === fromQuery)) {
      selectedId.value = fromQuery
    } else if (!selectedId.value && datasources.value.length) {
      const preferred = datasources.value.find((d) => d.name.includes('鉴数Demo')) || datasources.value[0]
      selectedId.value = preferred.id
    }
    if (selectedId.value) {
      await loadBrief()
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    loadError.value = err.response?.data?.detail || t('insight.loadFailed')
  } finally {
    pageLoading.value = false
  }
}

async function loadBrief() {
  if (!selectedId.value) {
    brief.value = null
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    try {
      brief.value = await insightApi.getDatasourceBrief(selectedId.value)
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status === 404 || err.response?.status === 405) {
        brief.value = await buildBrief(selectedId.value)
      } else {
        throw e
      }
    }
    if (!brief.value?.datasource?.id) {
      brief.value = await buildBrief(selectedId.value)
    }
  } catch (e: unknown) {
    brief.value = null
    const err = e as { response?: { data?: { detail?: string } } }
    loadError.value = err.response?.data?.detail || t('insight.loadFailed')
  } finally {
    loading.value = false
  }
}

function goBi() {
  router.push('/bi')
}

function goChat() {
  router.push('/')
}

function onProviderChange() {
  llmForm.value.endpoint_id = null
  llmForm.value.model = ''
}

function onEndpointChange() {
  llmForm.value.model = ''
  const ep = endpoints.value.find((e) => e.id === llmForm.value.endpoint_id)
  if (ep?.models?.length) {
    llmForm.value.model = ep.models[0]
  }
}

async function loadLlmSettings() {
  try {
    const [options, settingsRes] = await Promise.all([
      insightApi.getLlmOptions(),
      insightApi.getLlmSettings(),
    ])
    ollamaModels.value = options.ollama_models || []
    endpoints.value = options.endpoints || []
    chatCurrentLabel.value = settingsRes.chat_current?.label || settingsRes.chat_current?.model || ''
    effectiveLabel.value = settingsRes.effective?.label || ''
    llmForm.value = {
      use_chat_default: settingsRes.settings.use_chat_default,
      provider: (settingsRes.settings.provider as 'ollama' | 'openai_compatible') || 'ollama',
      model: settingsRes.settings.model || '',
      endpoint_id: settingsRes.settings.endpoint_id ?? null,
    }
  } catch {
  }
}

async function saveLlmSettings() {
  llmSaving.value = true
  try {
    const res = await insightApi.saveLlmSettings(llmForm.value)
    effectiveLabel.value = res.effective?.label || ''
    chatCurrentLabel.value = res.chat_current?.label || res.chat_current?.model || ''
    alert(t('insight.llmSavedNeedProfile'))
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    alert(err.response?.data?.detail || t('insight.llmSaveFailed'))
  } finally {
    llmSaving.value = false
  }
}

async function runProfile() {
  if (!selectedId.value) return
  profiling.value = true
  llmPanelOpen.value = false
  profilingMessage.value = t('insight.profilingProgress', { message: '…' })
  try {
    const res = await insightApi.startProfile(selectedId.value, {
      force: true,
      llm: { ...llmForm.value, persist: true },
    })
    await waitForProfileRun(res.run_id)
    await loadBrief()
    requestAnimationFrame(() => {
      document.querySelector('.profile-status-bar')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    alert(err.response?.data?.detail || t('bi.insightProfileFailed'))
  } finally {
    profiling.value = false
    profilingMessage.value = ''
  }
}

onMounted(async () => {
  await Promise.all([loadDatasources(), loadLlmSettings()])
})
</script>

<style scoped>
.insight-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  color: #e7e5e4;
}

.llm-panel {
  margin-bottom: 16px;
}

.llm-panel-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  color: #f5f5f4;
  list-style: none;
}

.llm-panel-summary::-webkit-details-marker {
  display: none;
}

.llm-summary-meta {
  font-size: 12px;
  font-weight: 400;
  text-align: right;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-status-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 24px 8px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.profile-status-bar.is-running {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(129, 140, 248, 0.35);
  color: #e0e7ff;
}

.profile-status-bar.is-ok {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(74, 222, 128, 0.35);
  color: #bbf7d0;
}

.profile-status-bar.is-fail {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.status-bar-label {
  color: #a8a29e;
  flex-shrink: 0;
}

.status-bar-value {
  flex: 1;
  min-width: 0;
  font-weight: 600;
}

.status-bar-refresh {
  flex-shrink: 0;
  margin-left: auto;
}

.scroll-hint {
  flex-shrink: 0;
  margin: 0 24px 6px;
  font-size: 12px;
  color: #a8a29e;
}

.llm-hint {
  margin: 0 0 12px;
}

.llm-radio {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
  cursor: pointer;
}

.chat-current {
  color: #a5b4fc;
  font-size: 13px;
}

.llm-custom {
  margin: 12px 0;
  display: grid;
  gap: 10px;
}

.llm-row {
  display: grid;
  gap: 6px;
}

.llm-row label {
  font-size: 12px;
  color: #a8a29e;
}

.llm-effective {
  margin: 12px 0;
  font-size: 14px;
  color: #d6d3d1;
}

.profiling-banner {
  margin: 10px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.35);
  font-size: 13px;
  color: #e0e7ff;
}

.llm-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.insight-header {
  flex-shrink: 0;
  padding: 20px 24px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.insight-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 32px;
}

.insight-header h1 {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 6px;
}

.subtitle {
  color: #a8a29e;
  font-size: 14px;
  margin: 0 0 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.ds-select {
  min-width: 260px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: #1c1917;
  color: #fafaf9;
}

.banner {
  padding: 12px 16px;
  border-radius: 10px;
  margin-bottom: 16px;
  font-size: 14px;
}

.banner-info {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(129, 140, 248, 0.35);
  color: #e0e7ff;
}

.banner-error {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  padding: 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-label {
  font-size: 12px;
  color: #a8a29e;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #fafaf9;
}

.stat-value.completed {
  color: #86efac;
}

.stat-value.failed {
  color: #fca5a5;
}

.panel {
  margin-bottom: 20px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.panel-warn {
  border-color: rgba(251, 191, 36, 0.35);
  background: rgba(251, 191, 36, 0.08);
}

.panel h2 {
  font-size: 15px;
  margin: 0 0 10px;
  color: #f5f5f4;
}

.list {
  margin: 0;
  padding-left: 20px;
  color: #d6d3d1;
  font-size: 14px;
}

.muted {
  color: #a8a29e;
  font-size: 14px;
}

.table-grid {
  display: grid;
  gap: 10px;
}

.table-card {
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.table-name {
  font-weight: 600;
  color: #fafaf9;
  margin-bottom: 4px;
}

.table-desc {
  font-size: 13px;
  color: #d6d3d1;
}

.examples {
  margin: 12px 0 16px;
  padding-left: 20px;
  color: #d6d3d1;
}

.empty-state {
  text-align: center;
  padding: 48px 16px;
  color: #a8a29e;
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.btn-primary,
.btn-secondary,
.btn-inline {
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background: #6366f1;
  border: none;
  color: white;
}

.btn-secondary {
  background: #292524;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fafaf9;
}

.btn-inline {
  margin-left: 12px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.25);
  color: inherit;
}

code {
  font-size: 12px;
  color: #c4b5fd;
}
</style>
