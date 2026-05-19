<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { MemoryEntityGraphNode } from '@/types'
import { useI18n } from '@/i18n'

const props = defineProps<{
  nodes: MemoryEntityGraphNode[]
  edges: Array<{ from: string; to: string; predicate: string; confidence: number }>
  loading?: boolean
  selectedId?: string | null
}>()

const emit = defineEmits<{
  (e: 'focus-entity', entityId: string): void
}>()

const { t } = useI18n()
const host = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const TYPE_COLORS: Record<string, string> = {
  person: '#f59e0b',
  project: '#38bdf8',
  concept: '#a78bfa',
  decision: '#34d399',
  org: '#fb7185',
  tech: '#94a3b8',
}

const render = () => {
  if (!host.value) return
  if (!chart) chart = echarts.init(host.value)

  const data = props.nodes.map((n) => ({
    id: n.id,
    name: n.label.length > 14 ? `${n.label.slice(0, 13)}…` : n.label,
    value: n.memory_count,
    symbolSize: Math.min(56, Math.max(18, 14 + Math.sqrt(n.memory_count || 0) * 8)),
    itemStyle: { color: TYPE_COLORS[n.type] || '#78716c' },
    label: { show: props.nodes.length <= 40 },
  }))

  const links = props.edges.map((e) => ({
    source: e.from,
    target: e.to,
    value: e.predicate,
    lineStyle: { opacity: 0.35 + (e.confidence || 0) * 0.35 },
  }))

  chart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (p: { data?: { id?: string; name?: string; value?: number } }) => {
          const d = p.data
          if (!d?.id) return ''
          return `${d.name || d.id}<br/>${t('memory.tree.statsMemories')}: ${d.value ?? 0}`
        },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          data,
          links,
          emphasis: { focus: 'adjacency' },
          force: {
            repulsion: 120,
            edgeLength: [40, 120],
            gravity: 0.08,
          },
          lineStyle: { color: 'rgba(251, 191, 36, 0.35)', curveness: 0.12 },
          edgeLabel: {
            show: props.edges.length <= 24,
            formatter: (p: { data?: { value?: string } }) => p.data?.value || '',
            fontSize: 9,
            color: '#a8a29e',
          },
        },
      ],
    },
    true
  )

  if (props.selectedId) {
    chart.dispatchAction({ type: 'highlight', seriesIndex: 0, name: data.find((d) => d.id === props.selectedId)?.name })
  }

  chart.off('click')
  chart.on('click', (params) => {
    const p = params as { dataType?: string; data?: { id?: string } }
    if (p.dataType === 'node' && p.data?.id) {
      emit('focus-entity', p.data.id)
    }
  })
}

const onResize = () => chart?.resize()

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.nodes, props.edges, props.selectedId, props.loading],
  () => {
    if (!props.loading) render()
  },
  { deep: true }
)
</script>

<template>
  <div class="relative flex min-h-[420px] flex-col">
    <div
      v-if="loading"
      class="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-[#171411]/80 text-sm text-stone-400"
    >
      {{ t('memory.loading') }}
    </div>
    <div
      v-if="!loading && !nodes.length"
      class="flex flex-1 items-center justify-center rounded-2xl border border-amber-100/10 bg-[#171411]/82 p-8 text-sm text-stone-400"
    >
      {{ t('memory.tree.graphEmpty') }}
    </div>
    <div
      v-show="nodes.length"
      ref="host"
      class="h-[min(560px,70vh)] w-full rounded-2xl border border-amber-100/10 bg-[#171411]/82"
    />
  </div>
</template>
