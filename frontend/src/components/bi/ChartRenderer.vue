<template>
  <div class="chart-renderer">
    <div v-if="chartType === 'table'" class="table-shell">
      <div v-if="tableColumns.length === 0" class="table-empty">
        {{ emptyText }}
      </div>
      <div v-else class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th v-if="showRowNumbers" class="col-index">#</th>
              <th
                v-for="col in tableColumns"
                :key="col.field"
                :class="{ 'col-numeric': isNumericColumn(col.field) }"
              >
                {{ col.header }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in tableData" :key="idx">
              <td v-if="showRowNumbers" class="col-index">{{ idx + 1 }}</td>
              <td
                v-for="col in tableColumns"
                :key="col.field"
                :class="cellClass(row[col.field], col.field)"
              >
                <span v-if="isNullish(row[col.field])" class="cell-null">NULL</span>
                <span v-else>{{ formatValue(row[col.field]) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-else ref="chartRef" class="echarts-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import * as echarts from 'echarts'

interface Props {
  chartType: string
  echartsOption: Record<string, any>
  rawData?: Record<string, any>[]
  title?: string
  showRowNumbers?: boolean
  emptyText?: string
}

const props = withDefaults(defineProps<Props>(), {
  showRowNumbers: true,
  emptyText: 'No rows returned',
})

const chartRef = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null

const tableColumns = computed(() => {
  if (props.chartType !== 'table' || !props.echartsOption?.columns) return []
  return props.echartsOption.columns as { field: string; header: string }[]
})

const tableData = computed(() => {
  if (props.chartType !== 'table' || !props.echartsOption?.data) return []
  return props.echartsOption.data as Record<string, any>[]
})

const numericColumns = computed(() => {
  const cols = new Set<string>()
  for (const col of tableColumns.value) {
    if (tableData.value.some((row) => isNumericValue(row[col.field]))) {
      cols.add(col.field)
    }
  }
  return cols
})

function isNullish(val: unknown): boolean {
  return val === null || val === undefined
}

function isNumericValue(val: unknown): boolean {
  if (typeof val === 'number' && Number.isFinite(val)) return true
  if (typeof val === 'string' && val.trim() !== '') {
    return /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(val.trim())
  }
  return false
}

function isNumericColumn(field: string): boolean {
  return numericColumns.value.has(field)
}

function cellClass(val: unknown, field: string): Record<string, boolean> {
  return {
    'col-numeric': isNumericColumn(field),
    'col-null': isNullish(val),
  }
}

function formatValue(val: unknown): string {
  if (isNullish(val)) return 'NULL'
  if (typeof val === 'boolean') return val ? 'true' : 'false'
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return String(val)
    if (Number.isInteger(val)) return val.toLocaleString()
    return val.toLocaleString(undefined, { maximumFractionDigits: 6 })
  }
  if (typeof val === 'object') {
    try {
      return JSON.stringify(val)
    } catch {
      return String(val)
    }
  }
  const text = String(val)
  if (isNumericValue(text)) {
    const num = Number(text)
    if (Number.isInteger(num)) return num.toLocaleString()
    return num.toLocaleString(undefined, { maximumFractionDigits: 6 })
  }
  return text
}

function initChart() {
  if (props.chartType === 'table') return
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const option = {
    ...props.echartsOption,
    title: props.title ? { text: props.title, left: 'center' } : props.echartsOption.title,
  }

  chartInstance.setOption(option, true)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  nextTick(() => {
    initChart()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})

watch(() => [props.chartType, props.echartsOption], () => {
  nextTick(() => {
    initChart()
  })
}, { deep: true })
</script>

<style scoped>
.chart-renderer {
  width: 100%;
}

.echarts-container {
  width: 100%;
  height: 400px;
}

.table-shell {
  border: 1px solid rgba(245, 158, 11, 0.14);
  border-radius: 10px;
  background: rgba(8, 7, 5, 0.55);
  overflow: hidden;
}

.table-scroll {
  max-height: min(520px, 60vh);
  overflow: auto;
}

.table-scroll::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.table-scroll::-webkit-scrollbar-thumb {
  background: rgba(245, 158, 11, 0.25);
  border-radius: 999px;
}

.table-scroll::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.04);
}

.data-table {
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
}

.data-table th,
.data-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  white-space: nowrap;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.data-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgba(28, 25, 23, 0.98);
  color: #fbbf24;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  text-transform: none;
  border-bottom: 1px solid rgba(245, 158, 11, 0.22);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
}

.data-table td {
  color: #e7e5e4;
  background: rgba(12, 11, 9, 0.72);
}

.data-table tbody tr:hover td {
  background: rgba(217, 119, 6, 0.08);
}

.data-table tbody tr:nth-child(even) td {
  background: rgba(255, 255, 255, 0.02);
}

.data-table tbody tr:nth-child(even):hover td {
  background: rgba(217, 119, 6, 0.1);
}

.col-index {
  position: sticky;
  left: 0;
  z-index: 1;
  min-width: 48px;
  width: 48px;
  text-align: center;
  color: #78716c !important;
  background: rgba(20, 17, 15, 0.98) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  font-variant-numeric: tabular-nums;
}

.data-table thead .col-index {
  z-index: 3;
  color: #a8a29e !important;
  background: rgba(28, 25, 23, 0.98) !important;
}

.col-numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.col-null {
  color: #57534e;
}

.cell-null {
  color: #78716c;
  font-style: italic;
}

.table-empty {
  padding: 32px 16px;
  text-align: center;
  color: #78716c;
  font-size: 14px;
}
</style>
