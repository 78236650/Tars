<template>
  <div class="chart-renderer">
    <div v-if="chartType === 'table'" class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="col in tableColumns" :key="col.field">{{ col.header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in tableData" :key="idx">
            <td v-for="col in tableColumns" :key="col.field">{{ formatValue(row[col.field]) }}</td>
          </tr>
        </tbody>
      </table>
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
}

const props = defineProps<Props>()

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

function formatValue(val: any): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') return Number.isInteger(val) ? val.toString() : val.toFixed(2)
  return String(val)
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

.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th,
.data-table td {
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  text-align: left;
}

.data-table th {
  background-color: #f9fafb;
  font-weight: 600;
  color: #374151;
}

.data-table tr:nth-child(even) {
  background-color: #f9fafb;
}

.data-table tr:hover {
  background-color: #f3f4f6;
}
</style>
