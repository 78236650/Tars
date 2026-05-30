<template>
  <div class="datasource-settings">
    <div class="header">
      <h2 class="title">{{ t('bi.datasourceTitle') }}</h2>
      <button class="btn-primary" @click="openCreateModal">+ {{ t('bi.createDatasource') }}</button>
    </div>

    <div v-if="loading" class="loading">{{ t('bi.loading') }}</div>
    <div v-else-if="datasources.length === 0" class="empty">{{ t('bi.empty') }}</div>
    <div v-else class="datasource-list">
      <div v-for="ds in datasources" :key="ds.id" class="datasource-card">
        <div class="card-header">
          <div class="ds-info">
            <span class="ds-name">{{ ds.name }}</span>
            <span class="ds-type">{{ ds.db_type }}</span>
          </div>
          <div class="ds-actions">
            <button
              class="btn-icon"
              :title="t('bi.testConnection')"
              :disabled="testingId === ds.id"
              @click="testConnection(ds.id)"
            >
              {{ testingId === ds.id ? '…' : '' }}<BaseIcon v-if="testingId !== ds.id" icon="lucide:plug" :size="14" />
            </button>
            <button
              class="btn-icon"
              :title="t('bi.editConnection')"
              @click="openEditModal(ds)"
            >
              <BaseIcon icon="lucide:settings" :size="14" />
            </button>
            <button
              class="btn-icon"
              :title="t('bi.refreshSchema')"
              :disabled="refreshingId === ds.id"
              @click="refreshSchema(ds.id)"
            >
              {{ refreshingId === ds.id ? '…' : '' }}<BaseIcon v-if="refreshingId !== ds.id" icon="lucide:refresh-cw" :size="14" />
            </button>
            <button
              class="btn-insight"
              :title="t('bi.insightProfile')"
              :disabled="profilingId === ds.id"
              @click="startInsightProfile(ds.id)"
            >
              {{ profilingId === ds.id ? t('bi.insightProfiling') : t('bi.insightProfileShort') }}
            </button>
            <button class="btn-insight btn-insight-outline" :title="t('insight.title')" @click="openInsightWorkbench(ds.id)">
              {{ t('insight.viewWorkbench') }}
            </button>
            <button class="btn-icon" :title="t('bi.editAnnotations')" @click="editAnnotations(ds)"><BaseIcon icon="lucide:pencil" :size="14" /></button>
            <button class="btn-icon btn-danger" :title="t('common.delete')" @click="deleteDataSource(ds.id)"><BaseIcon icon="lucide:trash-2" :size="14" /></button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="connectionSummary(ds)" class="connection-summary">
            {{ connectionSummary(ds) }}
          </div>
          <div class="schema-summary">
            {{ t('bi.tableCount', { count: Object.keys(ds.schema_snapshot?.tables || {}).length }) }}
          </div>
          <div v-if="ds.schema_annotations && Object.keys(ds.schema_annotations).length > 0" class="annotations-summary">
            {{ t('bi.annotatedCount', { count: Object.keys(ds.schema_annotations).length }) }}
          </div>
          <div v-if="insightRuns[ds.id]" class="insight-summary">
            <span class="insight-badge">{{ t('bi.insightForge') }}</span>
            <span :class="['insight-status', insightRuns[ds.id]?.status]">
              {{ insightStatusLabel(insightRuns[ds.id]) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <AppSurfaceDialog
      :open="showCreateModal"
      :title="t('bi.createTitle')"
      :description="t('bi.createDescription')"
      size="lg"
      @close="closeCreateModal"
    >
      <div class="space-y-4">
        <div class="form-group">
          <label>{{ t('bi.nameLabel') }}</label>
          <input v-model="createForm.name" type="text" :placeholder="t('bi.namePlaceholder')" />
        </div>
        <ConnectionFields v-model="createForm" />
      </div>

      <template #footer>
        <div class="surface-actions">
          <button class="btn-secondary" @click="closeCreateModal">{{ t('common.cancel') }}</button>
          <button class="btn-secondary" :disabled="testingConfig" @click="testCreateConfig">
            {{ testingConfig ? t('bi.testingConfig') : t('bi.testConfig') }}
          </button>
          <button class="btn-primary" :disabled="creating" @click="submitCreate">
            {{ creating ? t('bi.creating') : t('common.create') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <AppSurfaceDialog
      :open="showEditModal"
      :title="t('bi.editConnectionTitle')"
      :description="editTarget?.name"
      size="lg"
      @close="closeEditModal"
    >
      <div class="space-y-4">
        <ConnectionFields v-model="editForm" :password-optional="true" />
      </div>

      <template #footer>
        <div class="surface-actions">
          <button class="btn-secondary" @click="closeEditModal">{{ t('common.cancel') }}</button>
          <button class="btn-secondary" :disabled="testingConfig" @click="testEditConfig">
            {{ testingConfig ? t('bi.testingConfig') : t('bi.testConfig') }}
          </button>
          <button class="btn-primary" :disabled="savingEdit" @click="submitEdit">
            {{ savingEdit ? t('common.saving') : t('common.save') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <AppSurfaceDrawer
      :open="showAnnotatorModal"
      :title="selectedDataSource ? t('schemaAnnotator.title', { name: selectedDataSource.name }) : t('schemaAnnotator.titleFallback')"
      :description="t('schemaAnnotator.description')"
      side="right"
      @close="showAnnotatorModal = false"
    >
      <div class="schema-annotator-shell">
        <SchemaAnnotator
          :datasource="selectedDataSource"
          @save="onAnnotationsSave"
          @close="showAnnotatorModal = false"
        />
      </div>
    </AppSurfaceDrawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { biApi, insightApi } from '@/api'
import type { InsightProfileRunSummary } from '@/api'
import type { DataSource } from '@/types'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { useBiDataSources } from '@/composables/useBiDataSources'
import { getErrorDetail } from '@/utils/errorExtractor'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import AppSurfaceDrawer from '@/components/common/AppSurfaceDrawer.vue'
import SchemaAnnotator from './SchemaAnnotator.vue'
import ConnectionFields from './ConnectionFields.vue'
import { emptyConnectionForm, type ConnectionFormState } from './connectionForm'
import BaseIcon from '@/components/common/BaseIcon.vue'

const emit = defineEmits<{
  created: [id: string]
  changed: []
}>()

const { datasources, loadError, loading, loadDataSources: fetchDataSources } = useBiDataSources()
const insightRuns = ref<Record<string, InsightProfileRunSummary>>({})
const profilingId = ref('')
const testingId = ref('')
const refreshingId = ref('')
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showAnnotatorModal = ref(false)
const creating = ref(false)
const savingEdit = ref(false)
const testingConfig = ref(false)
const selectedDataSource = ref<DataSource | null>(null)
const editTarget = ref<DataSource | null>(null)
const { t } = useI18n()
const toast = useToast()
const router = useRouter()

const createForm = ref<ConnectionFormState & { name: string }>({
  name: '',
  ...emptyConnectionForm('mysql'),
})

const editForm = ref<ConnectionFormState>(emptyConnectionForm('mysql'))

function connectionSummary(ds: DataSource) {
  const conn = ds.connection
  if (!conn) return ''
  if (conn.db_type === 'sqlite') {
    return conn.database || ''
  }
  const host = conn.host || '127.0.0.1'
  const port = conn.port ?? ''
  const database = conn.database || ''
  return t('bi.connectionSummary', { host, port, database })
}

function insightStatusLabel(run: InsightProfileRunSummary | undefined) {
  if (!run) return ''
  const key = `bi.insightStatus.${run.status}` as const
  const translated = t(key)
  return translated === key ? run.status : translated
}

function openCreateModal() {
  createForm.value = { name: '', ...emptyConnectionForm('mysql') }
  showCreateModal.value = true
}

function closeCreateModal() {
  showCreateModal.value = false
}

function openEditModal(ds: DataSource) {
  editTarget.value = ds
  const conn = ds.connection
  editForm.value = {
    db_type: conn?.db_type || ds.db_type,
    host: conn?.host || '127.0.0.1',
    port: conn?.port ?? null,
    username: conn?.username || '',
    password: '',
    database: conn?.database || '',
  }
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
  editTarget.value = null
}

function connectionPayload(form: ConnectionFormState) {
  return {
    db_type: form.db_type,
    host: form.host,
    port: form.port,
    username: form.username,
    password: form.password,
    database: form.database,
  }
}

function validateConnectionForm(form: ConnectionFormState, requirePassword = true) {
  if (form.db_type === 'sqlite') {
    return Boolean(form.database?.trim())
  }
  if (!form.host?.trim() || !form.database?.trim()) return false
  if (requirePassword && !form.password) return false
  return true
}

async function loadInsightRunsForDatasource(dsId: string) {
  try {
    const res = await insightApi.listProfileRuns(dsId)
    const latest = res.runs?.[0]
    if (latest) {
      insightRuns.value = { ...insightRuns.value, [dsId]: latest }
    }
  } catch {
    // insight 模块未启用或无权时静默
  }
}

async function loadDataSources() {
  await fetchDataSources()
  if (loadError.value) {
    const detail = loadError.value
    if (detail.startsWith('bi.')) {
      toast.error(t(detail))
    } else {
      toast.error(`${t('bi.loadFailed')}: ${detail}`)
    }
  }
  insightRuns.value = {}
  await Promise.all(datasources.value.map((ds) => loadInsightRunsForDatasource(ds.id)))
  emit('changed')
}

async function testCreateConfig() {
  if (!validateConnectionForm(createForm.value)) {
    toast.error(t('bi.fillRequired'))
    return
  }
  testingConfig.value = true
  try {
    const res = await biApi.testConnectionConfig(connectionPayload(createForm.value))
    if (res.success) {
      toast.success(t('bi.connectionSuccess'))
    } else {
      toast.error(t('bi.connectionFailed', { message: res.message }))
    }
  } catch (e) {
    toast.error(t('bi.testFailed'))
  } finally {
    testingConfig.value = false
  }
}

async function submitCreate() {
  if (!createForm.value.name || !validateConnectionForm(createForm.value)) {
    toast.error(t('bi.fillRequired'))
    return
  }
  creating.value = true
  try {
    const res = await biApi.createDataSource({
      name: createForm.value.name,
      ...connectionPayload(createForm.value),
    })
    closeCreateModal()
    await loadDataSources()
    emit('created', res.datasource.id)
  } catch (e: any) {
    toast.error(t('bi.createFailed', { message: getErrorDetail(e) || e.message }))
  } finally {
    creating.value = false
  }
}

async function testEditConfig() {
  if (!validateConnectionForm(editForm.value, false)) {
    toast.error(t('bi.fillRequired'))
    return
  }
  testingConfig.value = true
  try {
    const res = await biApi.testConnectionConfig(connectionPayload(editForm.value))
    if (res.success) {
      toast.success(t('bi.connectionSuccess'))
    } else {
      toast.error(t('bi.connectionFailed', { message: res.message }))
    }
  } catch (e) {
    toast.error(t('bi.testFailed'))
  } finally {
    testingConfig.value = false
  }
}

async function submitEdit() {
  if (!editTarget.value || !validateConnectionForm(editForm.value, false)) {
    toast.error(t('bi.fillRequired'))
    return
  }
  savingEdit.value = true
  try {
    const payload = connectionPayload(editForm.value)
    if (!payload.password) {
      delete payload.password
    }
    await biApi.updateDataSource(editTarget.value.id, payload)
    closeEditModal()
    await loadDataSources()
    toast.success(t('bi.schemaRefreshSuccess'))
  } catch (e: any) {
    toast.error(getErrorDetail(e) || t('bi.refreshFailed'))
  } finally {
    savingEdit.value = false
  }
}

async function deleteDataSource(id: string) {
  if (!confirm(t('bi.deleteConfirm'))) return
  try {
    await biApi.deleteDataSource(id)
    await loadDataSources()
  } catch (e) {
    toast.error(t('bi.deleteFailed'))
  }
}

async function testConnection(id: string) {
  testingId.value = id
  try {
    const res = await biApi.testConnection(id)
    if (res.success) {
      toast.success(t('bi.connectionSuccess'))
    } else {
      toast.error(t('bi.connectionFailed', { message: res.message }))
    }
  } catch (e) {
    toast.error(t('bi.testFailed'))
  } finally {
    testingId.value = ''
  }
}

async function refreshSchema(id: string) {
  refreshingId.value = id
  try {
    await biApi.refreshSchema(id)
    toast.success(t('bi.schemaRefreshSuccess'))
    await loadDataSources()
  } catch (e) {
    toast.error(t('bi.refreshFailed'))
  } finally {
    refreshingId.value = ''
  }
}

function openInsightWorkbench(id: string) {
  router.push({ path: '/insight', query: { datasource_id: id } })
}

async function startInsightProfile(id: string) {
  profilingId.value = id
  try {
    const res = await insightApi.startProfile(id)
    toast.success(t('bi.insightProfileStarted', { runId: res.run_id }))
    await loadInsightRunsForDatasource(id)
    await loadDataSources()
  } catch (e: any) {
    toast.error(getErrorDetail(e, t('bi.insightProfileFailed')))
  } finally {
    profilingId.value = ''
  }
}

function editAnnotations(ds: DataSource) {
  selectedDataSource.value = ds
  showAnnotatorModal.value = true
}

async function onAnnotationsSave() {
  showAnnotatorModal.value = false
  await loadDataSources()
}

onMounted(loadDataSources)
</script>

<style scoped>
.datasource-settings {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #f5f0e8;
}

.btn-primary {
  background: #d97706;
  color: #0c0b09;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.btn-primary:hover {
  background: #f59e0b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: rgba(255,255,255,0.06);
  color: #d6d3d1;
  border: 1px solid rgba(255,255,255,0.08);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary:hover {
  background: rgba(255,255,255,0.1);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.datasource-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.datasource-card {
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 12px;
  padding: 16px;
  background: rgba(255,255,255,0.03);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.ds-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-name {
  font-weight: 600;
  font-size: 16px;
  color: #e7e5e4;
}

.ds-type {
  background: rgba(217, 119, 6, 0.15);
  color: #fbbf24;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.ds-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
  max-width: 55%;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  font-size: 16px;
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: wait;
}

.btn-icon:not(:disabled):hover {
  background: rgba(255,255,255,0.06);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.15);
}

.card-body {
  font-size: 13px;
  color: #78716c;
}

.connection-summary {
  margin-bottom: 4px;
  color: #a8a29e;
  word-break: break-all;
}

.schema-summary,
.annotations-summary {
  margin-top: 4px;
}

.insight-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 13px;
}

.insight-badge {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
}

.insight-status.completed {
  color: #86efac;
}

.insight-status.running,
.insight-status.pending {
  color: #fcd34d;
}

.insight-status.failed {
  color: #fca5a5;
}

.btn-insight {
  border: 1px solid rgba(129, 140, 248, 0.45);
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-insight:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.28);
}

.btn-insight:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-insight-outline {
  background: transparent;
  border-color: rgba(129, 140, 248, 0.35);
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #78716c;
}

.surface-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.schema-annotator-shell :deep(.annotator-header) {
  display: none;
}
</style>
