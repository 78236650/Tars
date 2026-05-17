<template>
  <div class="datasource-settings">
    <div class="header">
      <h2 class="title">{{ t('bi.datasourceTitle') }}</h2>
      <button class="btn-primary" @click="showCreateModal = true">+ {{ t('bi.createDatasource') }}</button>
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
            <button class="btn-icon" :title="t('bi.testConnection')" @click="testConnection(ds.id)">🔌</button>
            <button class="btn-icon" :title="t('bi.refreshSchema')" @click="refreshSchema(ds.id)">🔄</button>
            <button class="btn-icon" :title="t('bi.editAnnotations')" @click="editAnnotations(ds)">📝</button>
            <button class="btn-icon btn-danger" :title="t('common.delete')" @click="deleteDataSource(ds.id)">🗑️</button>
          </div>
        </div>
        <div class="card-body">
          <div class="schema-summary">
            {{ t('bi.tableCount', { count: Object.keys(ds.schema_snapshot.tables || {}).length }) }}
          </div>
          <div v-if="ds.schema_annotations && Object.keys(ds.schema_annotations).length > 0" class="annotations-summary">
            {{ t('bi.annotatedCount', { count: Object.keys(ds.schema_annotations).length }) }}
          </div>
        </div>
      </div>
    </div>

    <AppSurfaceDialog
      :open="showCreateModal"
      :title="t('bi.createTitle')"
      :description="t('bi.createDescription')"
      size="lg"
      @close="showCreateModal = false"
    >
      <div class="space-y-4">
        <div class="form-group">
          <label>{{ t('bi.nameLabel') }}</label>
          <input v-model="createForm.name" type="text" :placeholder="t('bi.namePlaceholder')" />
        </div>
        <div class="form-group">
          <label>{{ t('bi.dbTypeLabel') }}</label>
          <select v-model="createForm.db_type">
            <option value="mysql">MySQL</option>
            <option value="postgresql">PostgreSQL</option>
            <option value="sqlite">SQLite</option>
            <option value="clickhouse">ClickHouse</option>
            <option value="oracle">Oracle</option>
            <option value="sqlserver">SQL Server</option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('bi.connectionUrlLabel') }}</label>
          <input v-model="createForm.connection_url" type="text" :placeholder="t('bi.connectionPlaceholder')" />
          <div class="hint">
            MySQL: mysql+pymysql://user:pass@host:3306/db<br>
            PostgreSQL: postgresql+psycopg2://user:pass@host:5432/db<br>
            SQLite: sqlite:///path/to/db.db
          </div>
        </div>
      </div>

      <template #footer>
        <div class="surface-actions">
          <button class="btn-secondary" @click="showCreateModal = false">{{ t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="creating" @click="createDataSource">
            {{ creating ? t('bi.creating') : t('common.create') }}
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
import { biApi } from '@/api'
import type { DataSource } from '@/types'
import { useI18n } from '@/i18n'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import AppSurfaceDrawer from '@/components/common/AppSurfaceDrawer.vue'
import SchemaAnnotator from './SchemaAnnotator.vue'

const datasources = ref<DataSource[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const showAnnotatorModal = ref(false)
const creating = ref(false)
const selectedDataSource = ref<DataSource | null>(null)
const { t } = useI18n()

const createForm = ref({
  name: '',
  db_type: 'mysql',
  connection_url: '',
})

async function loadDataSources() {
  loading.value = true
  try {
    const res = await biApi.listDataSources()
    datasources.value = res.datasources
  } catch (e) {
    alert(t('bi.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function createDataSource() {
  if (!createForm.value.name || !createForm.value.connection_url) {
    alert(t('bi.fillRequired'))
    return
  }
  creating.value = true
  try {
    await biApi.createDataSource(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', db_type: 'mysql', connection_url: '' }
    await loadDataSources()
  } catch (e: any) {
    alert(t('bi.createFailed', { message: e.response?.data?.detail || e.message }))
  } finally {
    creating.value = false
  }
}

async function deleteDataSource(id: string) {
  if (!confirm(t('bi.deleteConfirm'))) return
  try {
    await biApi.deleteDataSource(id)
    await loadDataSources()
  } catch (e) {
    alert(t('bi.deleteFailed'))
  }
}

async function testConnection(id: string) {
  try {
    const res = await biApi.testConnection(id)
    alert(res.success ? t('bi.connectionSuccess') : t('bi.connectionFailed', { message: res.message }))
  } catch (e) {
    alert(t('bi.testFailed'))
  }
}

async function refreshSchema(id: string) {
  try {
    await biApi.refreshSchema(id)
    alert(t('bi.schemaRefreshSuccess'))
    await loadDataSources()
  } catch (e) {
    alert(t('bi.refreshFailed'))
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
  gap: 4px;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  font-size: 16px;
}

.btn-icon:hover {
  background: rgba(255,255,255,0.06);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.15);
}

.card-body {
  font-size: 13px;
  color: #78716c;
}

.schema-summary,
.annotations-summary {
  margin-top: 4px;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #78716c;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #d6d3d1;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
}

.form-group .hint {
  margin-top: 6px;
  font-size: 12px;
  color: #78716c;
  line-height: 1.5;
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
