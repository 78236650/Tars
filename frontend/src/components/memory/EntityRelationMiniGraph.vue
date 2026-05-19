<script setup lang="ts">
import { computed } from 'vue'
import type { EntityRelationEdge } from '@/types'

const props = defineProps<{
  centerLabel: string
  outgoing: EntityRelationEdge[]
  incoming: EntityRelationEdge[]
}>()

const emit = defineEmits<{
  (e: 'focus-entity', entityId: string): void
}>()

const edges = computed(() => [...props.outgoing, ...props.incoming])

const layout = computed(() => {
  const cx = 160
  const cy = 72
  const radius = 48
  const items = edges.value
  if (!items.length) return { cx, cy, center: props.centerLabel, nodes: [] as Array<{ x: number; y: number; label: string; id: string; predicate: string }> }

  return {
    cx,
    cy,
    center: props.centerLabel,
    nodes: items.map((edge, i) => {
      const angle = (Math.PI * 2 * i) / items.length - Math.PI / 2
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        label: edge.peer_label,
        id: edge.peer_entity,
        predicate: edge.predicate,
      }
    }),
  }
})
</script>

<template>
  <svg
    v-if="edges.length"
    viewBox="0 0 320 144"
    class="mt-3 w-full max-w-sm text-amber-200/90"
    role="img"
    aria-hidden="true"
  >
    <line
      v-for="(node, i) in layout.nodes"
      :key="'l' + i"
      :x1="layout.cx"
      :y1="layout.cy"
      :x2="node.x"
      :y2="node.y"
      stroke="currentColor"
      stroke-opacity="0.25"
      stroke-width="1"
    />
    <circle
      :cx="layout.cx"
      :cy="layout.cy"
      r="22"
      class="fill-amber-500/20 stroke-amber-400/50"
      stroke-width="1"
    />
    <text
      :x="layout.cx"
      :y="layout.cy + 4"
      text-anchor="middle"
      class="fill-stone-100 text-[9px]"
    >
      {{ layout.center.length > 10 ? layout.center.slice(0, 9) + '…' : layout.center }}
    </text>
    <g
      v-for="(node, i) in layout.nodes"
      :key="'n' + i"
      class="cursor-pointer"
      @click="emit('focus-entity', node.id)"
    >
      <circle
        :cx="node.x"
        :cy="node.y"
        r="16"
        class="fill-stone-800 stroke-amber-300/40 hover:fill-amber-500/20"
        stroke-width="1"
      />
      <text
        :x="node.x"
        :y="node.y + 3"
        text-anchor="middle"
        class="fill-stone-200 text-[8px] pointer-events-none"
      >
        {{ node.label.length > 8 ? node.label.slice(0, 7) + '…' : node.label }}
      </text>
    </g>
  </svg>
</template>
