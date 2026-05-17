<template>
  <div class="schema-annotator">
    <div class="annotator-header">
      <h3>{{ datasource?.name ? t('schemaAnnotator.title', { name: datasource.name }) : t('schemaAnnotator.titleFallback') }}</h3>
      <button class="btn-icon" @click="$emit('close')">✕</button>
    </div>

    <div v-if="!tables.length" class="empty">{{ t('schemaAnnotator.empty') }}</div>

    <div v-else class="tables-list">
      <div v-for="tableName in tables" :key="tableName" class="table-section">
        <div class="table-header" @click="toggleTable(tableName)">
          <span class="toggle-icon">{{ expandedTables[tableName] ? '▼' : '▶' }}</span>
          <span class="table-name">{{ tableName }}</span>
          <span v-if="getTableAnnotation(tableName)?.description" class="has-annotation">✓</span>
        </div>

        <div v-show="expandedTables[tableName]" class="table-content">
          <div class="annotation-row">
            <label>{{ t('schemaAnnotator.tableDescription') }}</label>
            <input
              v-model="editableAnnotations[tableName].description"
              type="text"
              :placeholder="t('schemaAnnotator.tableDescriptionPlaceholder')"
              @input="markDirty"
            />
          </div>

          <div class="columns-section">
            <div class="columns-header">{{ t('schemaAnnotator.columnAnnotations') }}</div>
            <div v-for="col in getColumns(tableName)" :key="col.name" class="column-row">
              <span class="col-name">{{ col.name }}</span>
              <span class="col-type">{{ col.type }}</span>
              <input
                v-model="editableAnnotations[tableName].columns[col.name]"
                type="text"
                :placeholder="t('schemaAnnotator.columnPlaceholder')"
                @input="markDirty"
              />
            </div>
          </div>

          <div class="annotation-row">
            <label>{{ t('schemaAnnotator.relationships') }}</label>
            <input
              v-model="editableAnnotations[tableName].relationships"
              type="text"
              :placeholder="t('schemaAnnotator.relationshipsPlaceholder')"
              @input="markDirty"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="annotator-actions">
      <button class="btn-secondary" @click="$emit('close')">{{ t('common.cancel') }}</button>
      <button class="btn-primary" :disabled="!dirty || saving" @click="saveAnnotations">
        {{ saving ? t('schemaAnnotator.saving') : t('common.save') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { biApi } from '@/api'
import type { DataSource } from '@/types'
import { useI18n } from '@/i18n'

interface Props {
  datasource: DataSource | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  save: []
  close: []
}>()

const expandedTables = ref<Record<string, boolean>>({})
const editableAnnotations = ref<Record<string, any>>({})
const dirty = ref(false)
const saving = ref(false)
const { t } = useI18n()

const tables = computed(() => {
  if (!props.datasource?.schema_snapshot?.tables) return []
  return Object.keys(props.datasource.schema_snapshot.tables)
})

function getColumns(tableName: string) {
  return props.datasource?.schema_snapshot?.tables?.[tableName]?.columns || []
}

function getTableAnnotation(tableName: string) {
  return props.datasource?.schema_annotations?.[tableName]
}

function toggleTable(tableName: string) {
  expandedTables.value[tableName] = !expandedTables.value[tableName]
}

function markDirty() {
  dirty.value = true
}

function initAnnotations() {
  const annotations: Record<string, any> = {}
  for (const tableName of tables.value) {
    const existing = props.datasource?.schema_annotations?.[tableName] || {}
    annotations[tableName] = {
      description: existing.description || '',
      columns: { ...(existing.columns || {}) },
      relationships: Array.isArray(existing.relationships) ? existing.relationships.join(', ') : (existing.relationships || ''),
    }
  }
  editableAnnotations.value = annotations
  dirty.value = false
}

async function saveAnnotations() {
  if (!props.datasource) return
  saving.value = true
  try {
    const payload: Record<string, any> = {}
    for (const [tableName, anno] of Object.entries(editableAnnotations.value)) {
      payload[tableName] = {
        description: anno.description,
        columns: anno.columns,
        relationships: anno.relationships ? anno.relationships.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      }
    }
    await biApi.updateAnnotations(props.datasource.id, payload)
    dirty.value = false
    emit('save')
  } catch (e) {
    alert(t('schemaAnnotator.saveFailed'))
  } finally {
    saving.value = false
  }
}

watch(() => props.datasource, () => {
  initAnnotations()
  for (const t of tables.value) {
    expandedTables.value[t] = false
  }
}, { immediate: true })
</script>

<style scoped>
.schema-annotator {
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

.annotator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.annotator-header h3 {
  font-size: 18px;
  margin: 0;
  color: #e7e5e4;
}

.tables-list {
  overflow-y: auto;
  flex: 1;
  max-height: 60vh;
}

.table-section {
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
}

.table-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  user-select: none;
}

.table-header:hover {
  background: rgba(255,255,255,0.06);
}

.toggle-icon {
  font-size: 12px;
  color: #78716c;
}

.table-name {
  font-weight: 500;
  color: #e7e5e4;
}

.has-annotation {
  color: #34d399;
  font-size: 14px;
}

.table-content {
  padding: 12px;
  border-top: 1px solid rgba(245, 158, 11, 0.1);
}

.annotation-row {
  margin-bottom: 12px;
}

.annotation-row label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #d6d3d1;
  margin-bottom: 4px;
}

.annotation-row input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.annotation-row input:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
}

.columns-section {
  margin-bottom: 12px;
}

.columns-header {
  font-size: 13px;
  font-weight: 500;
  color: #78716c;
  margin-bottom: 8px;
}

.column-row {
  display: grid;
  grid-template-columns: 120px 100px 1fr;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
}

.col-name {
  font-size: 13px;
  color: #e7e5e4;
  font-weight: 500;
}

.col-type {
  font-size: 12px;
  color: #78716c;
}

.column-row input {
  padding: 4px 8px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 4px;
  font-size: 13px;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.column-row input:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
}

.annotator-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(245, 158, 11, 0.1);
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

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  font-size: 16px;
  color: #78716c;
}

.btn-icon:hover {
  color: #e7e5e4;
}

.empty {
  text-align: center;
  padding: 40px;
  color: #78716c;
}
</style>
