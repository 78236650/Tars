<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
let resizeObserver: ResizeObserver | null = null

const TYPE_COLORS: Record<string, string> = {
  person: '#f59e0b',
  project: '#38bdf8',
  concept: '#a78bfa',
  decision: '#34d399',
  org: '#fb7185',
  tech: '#94a3b8',
}

const scheduleResize = () => {
  requestAnimationFrame(() => chart?.resize())
}

const highlightSelected = () => {
  if (!chart || !props.selectedId) return
  const idx = props.nodes.findIndex((n) => n.id === props.selectedId)
  if (idx < 0) return
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx })
}

const render = async () => {
  if (!host.value || !props.nodes.length) return
  await nextTick()
  if (!chart) chart = echarts.init(host.value)

  const nodeCount = props.nodes.length
  const data = props.nodes.map((n) => ({
    id: n.id,
    name: n.label.length > 14 ? `${n.label.slice(0, 13)}…` : n.label,
    value: n.memory_count,
    symbolSize: Math.min(52, Math.max(16, 12 + Math.sqrt(n.memory_count || 0) * 6)),
    itemStyle: { color: TYPE_COLORS[n.type] || '#78716c' },
    label: {
      show: nodeCount <= 48,
      fontSize: 10,
      color: '#e7e5e4',
    },
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
        confine: true,
        formatter: (p: { data?: { id?: string; name?: string; value?: number } }) => {
          const d = p.data
          if (!d?.id) return ''
          const full = props.nodes.find((n) => n.id === d.id)
          const title = full?.label || d.name || d.id
          return `${title}<br/>${t('memory.tree.statsMemories')}: ${d.value ?? 0}`
        },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          center: ['50%', '50%'],
          roam: true,
          scaleLimit: { min: 0.15, max: 6 },
          draggable: true,
          left: 24,
          right: 24,
          top: 24,
          bottom: 24,
          data,
          links,
          emphasis: { focus: 'adjacency', scale: 1.15 },
          force: {
            initLayout: 'circular',
            layoutAnimation: nodeCount <= 80,
            repulsion: Math.min(520, Math.max(160, nodeCount * 14)),
            edgeLength: [48, Math.min(160, 60 + nodeCount * 2)],
            gravity: 0.15,
            friction: 0.55,
          },
          lineStyle: { color: 'rgba(251, 191, 36, 0.35)', curveness: 0.12 },
          edgeLabel: {
            show: props.edges.length <= 28,
            formatter: (p: { data?: { value?: string } }) => p.data?.value || '',
            fontSize: 9,
            color: '#a8a29e',
          },
        },
      ],
    },
    true
  )

  highlightSelected()
  scheduleResize()

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
  if (host.value) {
    resizeObserver = new ResizeObserver(() => onResize())
    resizeObserver.observe(host.value)
  }
  if (!props.loading && props.nodes.length) void render()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.nodes, props.edges, props.loading],
  () => {
    if (props.loading) return
    if (!props.nodes.length) {
      chart?.clear()
      return
    }
    void render()
  },
  { deep: true }
)

watch(
  () => props.selectedId,
  () => highlightSelected()
)
</script>

<template>
  <div class="relative flex min-h-[360px] flex-1 flex-col">
    <div
      v-if="loading"
      class="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-surface-1/80 text-sm text-stone-400"
    >
      {{ t('memory.loading') }}
    </div>
    <div
      v-if="!loading && !nodes.length"
      class="flex min-h-[360px] flex-1 items-center justify-center rounded-2xl border border-amber-100/10 bg-surface-1/82 p-8 text-sm text-stone-400"
    >
      {{ t('memory.tree.graphEmpty') }}
    </div>
    <div
      v-show="nodes.length"
      ref="host"
      class="min-h-[360px] h-[520px] max-h-[calc(100vh-14rem)] w-full flex-1 rounded-2xl border border-amber-100/10 bg-surface-1/82"
    />
  </div>
</template>
