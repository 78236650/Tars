<template>
  <div class="bi-analytics-view">
    <div class="bi-header">
      <h1>{{ t('bi.title') }}</h1>
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', { active: currentTab === tab.key }]"
          @click="currentTab = tab.key"
        >
          {{ t(tab.labelKey) }}
        </button>
      </div>
    </div>

    <div class="bi-content">
      <DataSourceSettings v-if="currentTab === 'datasources'" />

      <div v-if="currentTab === 'query'" class="query-panel">
        <div class="query-toolbar">
          <select v-model="selectedDataSourceId" class="ds-select">
            <option value="">{{ t('bi.selectDataSource') }}</option>
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
              {{ ds.name }} ({{ ds.db_type }})
            </option>
          </select>
          <button class="btn-primary" :disabled="!canExecute" @click="executeQuery">
            {{ executing ? t('bi.executing') : t('bi.executeSql') }}
          </button>
          <button class="btn-secondary" :disabled="!canExecute" @click="generateChart">
            {{ charting ? t('bi.charting') : t('bi.generateChart') }}
          </button>
        </div>

        <div class="query-editor">
          <textarea
            v-model="sqlInput"
            class="sql-textarea"
            :placeholder="t('bi.sqlPlaceholder')"
            rows="6"
          />
        </div>

        <div v-if="queryError" class="error-message">
          {{ queryError }}
        </div>

        <div v-if="queryResult" class="result-panel">
          <div class="result-summary">
            {{ t('bi.rowsReturned', { count: queryResult.row_count }) }}
          </div>
          <ChartRenderer
            chart-type="table"
            :echarts-option="{ columns: queryResult.columns.map(c => ({ field: c, header: c })), data: queryResult.data }"
          />
        </div>

        <div v-if="chartResult" class="chart-panel">
          <div class="chart-summary">{{ chartResult.data_summary }}</div>
          <ChartRenderer
            :chart-type="chartResult.chart_type"
            :echarts-option="chartResult.echarts_option"
            :title="chartResult.title"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'
import { biApi } from '@/api'
import type { DataSource, BIQueryResult, BIChartResult } from '@/types'
import { useI18n } from '@/i18n'
import DataSourceSettings from '@/components/bi/DataSourceSettings.vue'
const ChartRenderer = defineAsyncComponent(() => import('@/components/bi/ChartRenderer.vue'))
const { t } = useI18n()

const tabs = [
  { key: 'datasources', labelKey: 'bi.tabDatasources' },
  { key: 'query', labelKey: 'bi.tabQuery' },
]

const currentTab = ref('datasources')
const datasources = ref<DataSource[]>([])
const selectedDataSourceId = ref('')
const sqlInput = ref('')
const executing = ref(false)
const charting = ref(false)
const queryResult = ref<BIQueryResult | null>(null)
const queryError = ref('')
const chartResult = ref<BIChartResult | null>(null)

const canExecute = computed(() => selectedDataSourceId.value && sqlInput.value.trim())

async function loadDataSources() {
  try {
    const res = await biApi.listDataSources()
    datasources.value = res.datasources
  } catch (e) {
    console.error('加载数据源失败', e)
  }
}

async function executeQuery() {
  if (!canExecute.value) return
  executing.value = true
  queryError.value = ''
  queryResult.value = null
  chartResult.value = null
  try {
    const res = await biApi.executeQuery(selectedDataSourceId.value, sqlInput.value.trim())
    if (res.success) {
      queryResult.value = res
    } else {
      queryError.value = res.error || t('common.error')
    }
  } catch (e: any) {
    queryError.value = e.response?.data?.detail || t('common.error')
  } finally {
    executing.value = false
  }
}

async function generateChart() {
  if (!canExecute.value) return
  charting.value = true
  queryError.value = ''
  chartResult.value = null
  try {
    const res = await biApi.generateChart(
      selectedDataSourceId.value,
      sqlInput.value.trim(),
      undefined,
      ''
    )
    chartResult.value = res
  } catch (e: any) {
    queryError.value = e.response?.data?.detail || t('common.error')
  } finally {
    charting.value = false
  }
}

onMounted(loadDataSources)
</script>

<style scoped>
.bi-analytics-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.bi-header {
  background: rgba(20, 17, 15, 0.82);
  border-bottom: 1px solid rgba(245, 158, 11, 0.1);
  padding: 16px 24px;
  border-radius: 16px 16px 0 0;
}

.bi-header h1 {
  font-size: 20px;
  font-weight: 600;
  color: #f5f0e8;
  margin: 0 0 12px 0;
}

.tabs {
  display: flex;
  gap: 8px;
}

.tab-btn {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
}

.tab-btn:hover {
  background: rgba(255,255,255,0.06);
  color: #d6d3d1;
}

.tab-btn.active {
  background: rgba(217, 119, 6, 0.16);
  color: #fbbf24;
  font-weight: 500;
}

.bi-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.query-panel {
  background: rgba(20, 17, 15, 0.72);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid rgba(245, 158, 11, 0.1);
}

.query-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.ds-select {
  padding: 8px 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-size: 14px;
  min-width: 200px;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.sql-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
  background: rgba(8, 7, 5, 0.72);
  color: #e7e5e4;
}

.sql-textarea:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
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

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border-radius: 6px;
  font-size: 14px;
}

.result-panel,
.chart-panel {
  margin-top: 20px;
}

.result-summary,
.chart-summary {
  font-size: 14px;
  color: #78716c;
  margin-bottom: 12px;
}
</style>
