<template>
  <div class="bi-analytics-view">
    <div class="bi-header">
      <h1>BI 数据分析</h1>
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', { active: currentTab === tab.key }]"
          @click="currentTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="bi-content">
      <DataSourceSettings v-if="currentTab === 'datasources'" />

      <div v-if="currentTab === 'query'" class="query-panel">
        <div class="query-toolbar">
          <select v-model="selectedDataSourceId" class="ds-select">
            <option value="">选择数据源</option>
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
              {{ ds.name }} ({{ ds.db_type }})
            </option>
          </select>
          <button class="btn-primary" :disabled="!canExecute" @click="executeQuery">
            {{ executing ? '执行中...' : '执行 SQL' }}
          </button>
          <button class="btn-secondary" :disabled="!canExecute" @click="generateChart">
            {{ charting ? '生成中...' : '生成图表' }}
          </button>
        </div>

        <div class="query-editor">
          <textarea
            v-model="sqlInput"
            class="sql-textarea"
            placeholder="输入 SQL 查询语句（仅支持 SELECT）..."
            rows="6"
          />
        </div>

        <div v-if="queryError" class="error-message">
          {{ queryError }}
        </div>

        <div v-if="queryResult" class="result-panel">
          <div class="result-summary">
            返回 {{ queryResult.row_count }} 行数据
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
import { ref, onMounted, computed } from 'vue'
import { biApi } from '@/api'
import type { DataSource, BIQueryResult, BIChartResult } from '@/types'
import DataSourceSettings from '@/components/bi/DataSourceSettings.vue'
import ChartRenderer from '@/components/bi/ChartRenderer.vue'

const tabs = [
  { key: 'datasources', label: '数据源管理' },
  { key: 'query', label: 'SQL 查询' },
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
      queryError.value = res.error || '查询失败'
    }
  } catch (e: any) {
    queryError.value = e.response?.data?.detail || '执行失败'
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
    queryError.value = e.response?.data?.detail || '图表生成失败'
  } finally {
    charting.value = false
  }
}

onMounted(loadDataSources)
</script>

<style scoped>
.bi-analytics-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f3f4f6;
}

.bi-header {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 24px;
}

.bi-header h1 {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
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
  color: #6b7280;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
}

.tab-btn:hover {
  background: #f3f4f6;
}

.tab-btn.active {
  background: #dbeafe;
  color: #1e40af;
  font-weight: 500;
}

.bi-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.query-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
}

.query-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.ds-select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  min-width: 200px;
}

.sql-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
}

.sql-textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary:hover {
  background: #d1d5db;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: #fee2e2;
  color: #991b1b;
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
  color: #6b7280;
  margin-bottom: 12px;
}
</style>
