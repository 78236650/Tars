<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import type { InsightDatasourceBrief } from '@/api'

const props = defineProps<{
  open: boolean
  brief: InsightDatasourceBrief | null
}>()

const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()

const tableRows = computed(() => {
  const annotations = props.brief?.schema_annotations || {}
  const snapshot = props.brief?.insight_snapshot as { tables?: Record<string, unknown> } | undefined
  const tableKeys = new Set([
    ...Object.keys(annotations),
    ...Object.keys(snapshot?.tables || {}),
  ])
  return Array.from(tableKeys)
    .slice(0, 40)
    .map((name) => {
      const ann = annotations[name] as { description?: string; business_name?: string } | undefined
      return {
        name,
        label: ann?.business_name || name,
        description: ann?.description || '—',
      }
    })
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="drawer-backdrop" @click.self="emit('close')">
      <aside class="drawer-panel">
        <header class="drawer-header">
          <h2>{{ t('insight.schemaPreview.title') }}</h2>
          <button type="button" class="drawer-close" @click="emit('close')">×</button>
        </header>
        <p class="drawer-hint">{{ t('insight.schemaPreview.hint') }}</p>
        <p v-if="brief?.datasource" class="drawer-meta">
          {{ brief.datasource.name }} · {{ brief.datasource.table_count }} {{ t('insight.tables') }}
        </p>
        <div v-if="!tableRows.length" class="drawer-empty">{{ t('insight.schemaPreview.empty') }}</div>
        <ul v-else class="table-list">
          <li v-for="row in tableRows" :key="row.name" class="table-row">
            <div class="table-name">{{ row.label }}</div>
            <code class="table-code">{{ row.name }}</code>
            <p class="table-desc">{{ row.description }}</p>
          </li>
        </ul>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  justify-content: flex-end;
}
.drawer-panel {
  width: min(420px, 92vw);
  height: 100%;
  background: #1c1917;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  padding: 16px 18px;
  overflow: hidden;
}
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.drawer-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #fafaf9;
  margin: 0;
}
.drawer-close {
  font-size: 22px;
  line-height: 1;
  color: #a8a29e;
  background: none;
  border: none;
  cursor: pointer;
}
.drawer-hint,
.drawer-meta {
  font-size: 12px;
  color: #a8a29e;
  margin: 0 0 12px;
}
.drawer-empty {
  color: #78716c;
  font-size: 13px;
}
.table-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}
.table-row {
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.table-name {
  font-size: 14px;
  color: #f5f5f4;
  font-weight: 500;
}
.table-code {
  font-size: 11px;
  color: #78716c;
}
.table-desc {
  font-size: 12px;
  color: #d6d3d1;
  margin: 4px 0 0;
}
</style>
