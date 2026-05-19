<script setup lang="ts">
import type { MemoryTreeNode } from '@/types'

defineOptions({ name: 'MemoryTreeNode' })

const props = defineProps<{
  node: MemoryTreeNode
  depth: number
  expandedIds: Set<string>
  selectedId: string | null
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'select', node: MemoryTreeNode): void
}>()

const hasChildren = () => props.node.children.length > 0
const expanded = () => props.expandedIds.has(props.node.id)
const selected = () => props.selectedId === props.node.id

const suffix = () => {
  if (props.node.kind === 'entity' && props.node.meta.memory_count != null) {
    return ` (${props.node.meta.memory_count})`
  }
  if (props.node.kind === 'bucket' && props.node.meta.count != null) {
    return ` (${props.node.meta.count})`
  }
  if (props.node.kind === 'compressed' && props.node.meta.source_count != null) {
    return ` (${props.node.meta.source_count})`
  }
  return ''
}

const onRowClick = () => {
  emit('select', props.node)
  if (hasChildren()) emit('toggle', props.node.id)
}
</script>

<template>
  <li>
    <button
      type="button"
      class="flex w-full items-center gap-1 rounded-lg px-2 py-1.5 text-left text-sm transition"
      :class="selected() ? 'bg-amber-500/15 text-amber-100' : 'text-stone-300 hover:bg-white/[0.04]'"
      :style="{ paddingLeft: `${depth * 12 + 8}px` }"
      @click="onRowClick"
    >
      <span
        v-if="hasChildren()"
        class="w-4 shrink-0 text-xs text-stone-500"
        @click.stop="emit('toggle', node.id)"
      >
        {{ expanded() ? '▼' : '▶' }}
      </span>
      <span v-else class="w-4 shrink-0" />
      <span class="truncate">{{ node.label }}{{ suffix() }}</span>
    </button>
    <ul v-if="hasChildren() && expanded()">
      <MemoryTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :expanded-ids="expandedIds"
        :selected-id="selectedId"
        @toggle="emit('toggle', $event)"
        @select="emit('select', $event)"
      />
    </ul>
  </li>
</template>
