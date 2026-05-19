<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { MemoryTreeNode } from '@/types'
import type { FlatTreeRow } from './memoryTreeFlatten'

const props = defineProps<{
  rows: FlatTreeRow[]
  expandedIds: Set<string>
  selectedId: string | null
  rowHeight?: number
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'select', node: MemoryTreeNode): void
}>()

const ROW_H = () => props.rowHeight ?? 32
const OVERSCAN = 8

const scroller = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportHeight = ref(400)

const updateViewport = () => {
  if (scroller.value) viewportHeight.value = scroller.value.clientHeight || 400
}

let ro: ResizeObserver | null = null
onMounted(() => {
  updateViewport()
  ro = new ResizeObserver(() => updateViewport())
  if (scroller.value) ro.observe(scroller.value)
})
onUnmounted(() => ro?.disconnect())

const onScroll = () => {
  if (scroller.value) scrollTop.value = scroller.value.scrollTop
}

watch(
  () => props.rows.length,
  () => {
    scrollTop.value = scroller.value?.scrollTop ?? 0
  }
)

const windowRange = computed(() => {
  const rh = ROW_H()
  const total = props.rows.length
  if (!total) return { start: 0, end: 0, paddingTop: 0, paddingBottom: 0 }
  const start = Math.max(0, Math.floor(scrollTop.value / rh) - OVERSCAN)
  const visible = Math.ceil(viewportHeight.value / rh) + OVERSCAN * 2
  const end = Math.min(total, start + visible)
  return {
    start,
    end,
    paddingTop: start * rh,
    paddingBottom: Math.max(0, (total - end) * rh),
  }
})

const visibleRows = computed(() =>
  props.rows.slice(windowRange.value.start, windowRange.value.end)
)

const suffix = (node: MemoryTreeNode) => {
  if (node.kind === 'entity' && node.meta.memory_count != null) {
    return ` (${node.meta.memory_count})`
  }
  if (node.kind === 'bucket' && node.meta.count != null) {
    return ` (${node.meta.count})`
  }
  if (node.kind === 'compressed' && node.meta.source_count != null) {
    return ` (${node.meta.source_count})`
  }
  return ''
}

const hasChildren = (node: MemoryTreeNode) => node.children.length > 0
const expanded = (id: string) => props.expandedIds.has(id)
const selected = (id: string) => props.selectedId === id

const onRowClick = (node: MemoryTreeNode) => {
  emit('select', node)
  if (hasChildren(node)) emit('toggle', node.id)
}
</script>

<template>
  <div
    ref="scroller"
    class="h-full min-h-[200px] overflow-y-auto"
    @scroll="onScroll"
  >
    <div :style="{ height: `${windowRange.paddingTop}px` }" />
    <button
      v-for="{ node, depth } in visibleRows"
      :key="node.id"
      type="button"
      class="flex w-full items-center gap-1 rounded-lg px-2 text-left text-sm transition"
      :class="selected(node.id) ? 'bg-amber-500/15 text-amber-100' : 'text-stone-300 hover:bg-white/[0.04]'"
      :style="{
        height: `${ROW_H()}px`,
        paddingLeft: `${depth * 12 + 8}px`,
      }"
      @click="onRowClick(node)"
    >
      <span
        v-if="hasChildren(node)"
        class="w-4 shrink-0 text-xs text-stone-500"
        @click.stop="emit('toggle', node.id)"
      >
        {{ expanded(node.id) ? '▼' : '▶' }}
      </span>
      <span v-else class="w-4 shrink-0" />
      <span class="truncate">{{ node.label }}{{ suffix(node) }}</span>
    </button>
    <div :style="{ height: `${windowRange.paddingBottom}px` }" />
  </div>
</template>
