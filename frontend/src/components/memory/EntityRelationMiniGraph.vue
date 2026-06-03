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

const NODE_R = 18
const CENTER_R = 24

const layout = computed(() => {
  const items = edges.value
  const count = items.length
  const radius = count <= 1 ? 0 : Math.max(56, Math.min(96, 40 + count * 9))
  const pad = NODE_R + 12
  const width = Math.max(280, (radius + CENTER_R + pad) * 2 + 48)
  const height = Math.max(160, (radius + CENTER_R + pad) * 2 + 40)
  const cx = width / 2
  const cy = height / 2

  if (!count) {
    return { width, height, cx, cy, center: props.centerLabel, nodes: [] as Array<{
      x: number
      y: number
      label: string
      id: string
      predicate: string
    }> }
  }

  return {
    width,
    height,
    cx,
    cy,
    center: props.centerLabel,
    nodes: items.map((edge, i) => {
      const angle = (Math.PI * 2 * i) / count - Math.PI / 2
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

const truncate = (text: string, max: number) =>
  text.length > max ? `${text.slice(0, max - 1)}…` : text
</script>

<template>
  <svg
    v-if="edges.length"
    :viewBox="`0 0 ${layout.width} ${layout.height}`"
    class="mt-3 w-full text-amber-200/90"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    :aria-label="layout.center"
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
      :r="CENTER_R"
      class="fill-amber-500/20 stroke-amber-400/50"
      stroke-width="1"
    />
    <text
      :x="layout.cx"
      :y="layout.cy + 4"
      text-anchor="middle"
      class="fill-stone-100 text-[10px]"
    >
      {{ truncate(layout.center, 14) }}
    </text>
    <g
      v-for="(node, i) in layout.nodes"
      :key="'n' + i"
      class="cursor-pointer"
      @click="emit('focus-entity', node.id)"
    >
      <title>{{ node.label }} — {{ node.predicate }}</title>
      <circle
        :cx="node.x"
        :cy="node.y"
        :r="NODE_R"
        class="fill-stone-800 stroke-amber-300/40 hover:fill-amber-500/20"
        stroke-width="1"
      />
      <text
        :x="node.x"
        :y="node.y + 3"
        text-anchor="middle"
        class="fill-stone-200 text-[9px] pointer-events-none"
      >
        {{ truncate(node.label, 10) }}
      </text>
    </g>
  </svg>
</template>
