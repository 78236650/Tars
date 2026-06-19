<template>
  <div class="report-view p-6">
    <h1 class="text-xl font-bold mb-4">数据报表</h1>

    <div class="flex gap-4 mb-4 items-end flex-wrap">
      <div>
        <label class="block text-xs text-stone-400 mb-1">数据源</label>
        <select v-model="datasourceId" class="ds-select">
          <option value="">选择数据源</option>
          <option v-for="ds in datasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
        </select>
      </div>
      <div>
        <label class="block text-xs text-stone-400 mb-1">表名</label>
        <input v-model="tableName" class="ds-select" placeholder="表名" />
      </div>
      <div>
        <label class="block text-xs text-stone-400 mb-1">图表类型</label>
        <select v-model="spec.chart_type" class="ds-select">
          <option v-for="ct in chartTypes" :key="ct" :value="ct">{{ ct }}</option>
        </select>
      </div>
      <button @click="executeChart" class="btn-primary" :disabled="!canExecute">
        执行
      </button>
      <button @click="showSave = true" class="btn-secondary" :disabled="!chartResult">
        保存图表
      </button>
    </div>

    <!-- 维度 / 度量 -->
    <div class="flex gap-4 mb-4">
      <div class="flex-1">
        <label class="block text-xs text-stone-400 mb-1">维度 (dimensions)</label>
        <div class="flex gap-2 flex-wrap">
          <span v-for="(d, i) in spec.dimensions" :key="i" class="inline-flex items-center gap-1 bg-white/[0.06] rounded px-2 py-1 text-sm">
            {{ d.field }}
            <button @click="spec.dimensions.splice(i,1)" class="text-red-400">×</button>
          </span>
        </div>
        <input v-model="newDim" @keyup.enter="addDim" class="ds-select mt-1 w-40" placeholder="字段名 + Enter" />
      </div>
      <div class="flex-1">
        <label class="block text-xs text-stone-400 mb-1">度量 (measures)</label>
        <div class="flex gap-2 flex-wrap">
          <span v-for="(m, i) in spec.measures" :key="i" class="inline-flex items-center gap-1 bg-white/[0.06] rounded px-2 py-1 text-sm">
            {{ m.agg }}({{ m.field }})
            <button @click="spec.measures.splice(i,1)" class="text-red-400">×</button>
          </span>
        </div>
        <div class="flex gap-1 mt-1">
          <input v-model="newMeasField" class="ds-select w-32" placeholder="字段" />
          <select v-model="newMeasAgg" class="ds-select w-28">
            <option v-for="a in aggs" :key="a" :value="a">{{ a }}</option>
          </select>
          <button @click="addMeas" class="btn-secondary text-xs px-2">+</button>
        </div>
      </div>
    </div>

    <!-- 图表结果 -->
    <div v-if="chartResult" class="mt-4">
      <div v-if="chartResult.truncated" class="text-amber-400 text-sm mb-2">⚠ 数据已截断（抽样展示）</div>
      <div
        v-if="showEcharts"
        ref="chartEl"
        class="bg-white/[0.04] rounded-lg p-4 h-80 w-full mb-4"
      />
      <div class="bg-white/[0.04] rounded-lg p-4 overflow-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-stone-400 text-left">
              <th class="p-2">类别</th>
              <th v-for="s in chartResult.series" :key="s.name" class="p-2">{{ s.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(cat, i) in chartResult.categories" :key="i" class="border-t border-amber-100/10">
              <td class="p-2">{{ cat }}</td>
              <td v-for="s in chartResult.series" :key="s.name" class="p-2">{{ s.data[i] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 已保存图表 -->
    <div v-if="savedCharts.length" class="mt-6">
      <h2 class="text-lg font-semibold mb-2">已保存图表</h2>
      <ul class="space-y-1">
        <li v-for="c in savedCharts" :key="c.id" class="flex justify-between items-center bg-white/[0.04] rounded p-2 text-sm">
          <span>{{ c.name }} ({{ c.chart_type }})</span>
          <button @click="deleteChart(c.id)" class="text-red-400 hover:text-red-300 text-xs">删除</button>
        </li>
      </ul>
    </div>

    <!-- 保存弹窗 -->
    <div v-if="showSave" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-stone-800 rounded-xl p-6 w-full max-w-sm">
        <h3 class="text-lg font-semibold mb-4">保存图表</h3>
        <input v-model="chartName" class="ds-select w-full mb-4" placeholder="图表名称" />
        <div class="flex gap-2 justify-end">
          <button @click="showSave = false" class="btn-secondary">取消</button>
          <button @click="saveChart" class="btn-primary" :disabled="!chartName">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { reportApi } from '@/api/report'
import type { ChartSpecDef, ChartData, SavedChart } from '@/api/report'
import { useBiDataSources } from '@/composables/useBiDataSources'

const { datasources, loadDataSources } = useBiDataSources()
const aggs = ['sum', 'avg', 'count', 'min', 'max', 'count_distinct']

const datasourceId = ref('')
const tableName = ref('')
const chartTypes = ref<string[]>([])
const newDim = ref('')
const newMeasField = ref('')
const newMeasAgg = ref('sum')
const chartName = ref('')
const showSave = ref(false)
const chartResult = ref<ChartData | null>(null)
const savedCharts = ref<SavedChart[]>([])
const chartEl = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const spec = reactive<ChartSpecDef>({
  chart_type: 'bar',
  dimensions: [],
  measures: [],
})

const canExecute = computed(() => datasourceId.value && tableName.value && spec.measures.length > 0)
const showEcharts = computed(() =>
  chartResult.value &&
  ['bar', 'line', 'pie'].includes(spec.chart_type) &&
  chartResult.value.categories.length > 0
)

function renderChart() {
  if (!chartEl.value || !chartResult.value || !showEcharts.value) return
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  chartInstance = echarts.init(chartEl.value)
  const data = chartResult.value
  const type = spec.chart_type
  let option: echarts.EChartsOption
  if (type === 'pie' && data.series[0]) {
    option = {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: data.categories.map((cat, i) => ({ name: String(cat), value: data.series[0].data[i] })),
      }],
    }
  } else {
    option = {
      tooltip: { trigger: 'axis' },
      legend: { data: data.series.map((s) => s.name), textStyle: { color: '#a8a29e' } },
      xAxis: { type: 'category', data: data.categories, axisLabel: { color: '#a8a29e' } },
      yAxis: { type: 'value', axisLabel: { color: '#a8a29e' } },
      series: data.series.map((s) => ({
        name: s.name,
        type: type === 'line' ? 'line' : 'bar',
        data: s.data,
      })),
    }
  }
  chartInstance.setOption(option)
}

watch([chartResult, () => spec.chart_type], async () => {
  await nextTick()
  renderChart()
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
})

function addDim() {
  if (newDim.value.trim()) {
    spec.dimensions.push({ field: newDim.value.trim() })
    newDim.value = ''
  }
}

function addMeas() {
  if (newMeasField.value.trim()) {
    spec.measures.push({ field: newMeasField.value.trim(), agg: newMeasAgg.value })
    newMeasField.value = ''
  }
}

onMounted(async () => {
  await loadDataSources()
  chartTypes.value = await reportApi.chartTypes()
})

async function executeChart() {
  chartResult.value = await reportApi.executeChart({
    datasource_id: datasourceId.value,
    table_name: tableName.value,
    spec: JSON.parse(JSON.stringify(spec)),
  })
}

async function saveChart() {
  await reportApi.createChart({
    datasource_id: datasourceId.value,
    table_name: tableName.value,
    name: chartName.value,
    chart_type: spec.chart_type,
    spec: JSON.parse(JSON.stringify(spec)),
  })
  showSave.value = false
  chartName.value = ''
  savedCharts.value = await reportApi.listCharts(datasourceId.value)
}

async function deleteChart(id: string) {
  await reportApi.deleteChart(id)
  savedCharts.value = await reportApi.listCharts(datasourceId.value)
}
</script>

<style scoped>
.ds-select {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(217,119,6,0.1);
  color: #d6d3d1;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}
.ds-select:focus { outline: none; border-color: rgba(217,119,6,0.4); }
.btn-primary { background: #d97706; color: #1c1917; padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 500; }
.btn-primary:disabled { opacity: 0.4; }
.btn-secondary { background: rgba(255,255,255,0.06); color: #d6d3d1; padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.875rem; }
.btn-secondary:hover { background: rgba(255,255,255,0.1); }
</style>
