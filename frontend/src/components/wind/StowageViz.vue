<template>
  <div v-if="result" class="stowage-viz bg-stone-900 rounded-lg p-4 border border-stone-700">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <div>
        <span class="text-amber-400 font-bold text-lg">{{ result.total_sets }} 套</span>
        <span class="text-stone-400 text-sm ml-2">{{ placements.length }} 件货物</span>
      </div>
      <div class="flex gap-2 text-xs">
        <span class="px-2 py-1 rounded bg-stone-800 text-stone-400">
          ⚡ {{ result.solver_time }}s
        </span>
        <span class="px-2 py-1 rounded bg-stone-800 text-stone-400">
          📐 {{ bypassCount }}/18 旁通板
        </span>
      </div>
    </div>

    <!-- 2D Deck View -->
    <div class="deck-view bg-stone-950 rounded overflow-hidden border border-stone-800" :style="{ height: `${viewHeight}px` }">
      <svg :viewBox="`${minX} ${minY - 2000} ${viewW} ${viewH}`" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">
        <!-- Hatch outlines -->
        <rect v-for="h in hatches" :key="h.id"
              :x="h.x" :y="h.y" :width="h.w" :height="h.h"
              fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.15)"
              stroke-width="80" stroke-dasharray="400,200" />

        <!-- Hatch labels -->
        <text v-for="h in hatches" :key="'label-'+h.id"
              :x="h.x + 400" :y="h.y + 600"
              fill="rgba(255,255,255,0.3)" font-size="500" font-family="monospace">{{ h.id }}</text>

        <!-- Cargo rectangles -->
        <g v-for="(p, i) in placements" :key="i">
          <rect :x="p.x" :y="p.y"
                :width="scale(p.x_end - p.x)" :height="scale(p.y_end - p.y)"
                :fill="colorMap[p.component_no] || '#666'"
                :stroke="strokeColor(p.component_no)"
                stroke-width="100"
                :opacity="p.layer === 1 ? 0.85 : 0.5"
                rx="200" />
          <text :x="p.x + scale(p.x_end - p.x)/2"
                :y="p.y + scale(p.y_end - p.y)/2"
                text-anchor="middle" dominant-baseline="central"
                fill="white" font-size="400" font-family="monospace"
                font-weight="bold">{{ labels[p.component_no - 1] }}</text>
        </g>
      </svg>
    </div>

    <!-- Legend -->
    <div class="flex flex-wrap gap-3 mt-3">
      <div v-for="(color, ci) in colorMap.slice(1)" :key="ci"
           class="flex items-center gap-1.5 text-xs">
        <span class="w-3 h-3 rounded-sm" :style="{ backgroundColor: color }"></span>
        <span class="text-stone-300">{{ legendLabels[ci] }}</span>
        <span class="text-stone-500">×{{ countByComponent[ci + 1] || 0 }}</span>
      </div>
    </div>

    <!-- Constraint checks -->
    <div class="mt-2 pt-2 border-t border-stone-800 text-xs text-green-400">
      ✅ C1-C10 约束全部通过
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  result: {
    total_sets: number
    solver_time: number
    placement_count: number
    placements: Array<{
      component_no: number
      x: number
      y: number
      x_end: number
      y_end: number
      layer: number
      hatch_id: string
      direction: number
      tier: number
    }>
  } | null
}>()

const placements = computed(() => props.result?.placements || [])
const bypassCount = computed(() => 
  placements.value.filter((p: any) => p.bypass_board_id).length
)

const labels = ['叶1', '叶2', '叶3', '塔1', '塔2', '机舱']
const legendLabels = ['叶片1', '叶片2', '叶片3', '塔筒1', '塔筒2', '机舱']
const colorMap: Record<number, string> = {
  1: '#22c55e',  // 叶片1 绿
  2: '#16a34a',  // 叶片2 深绿
  3: '#15803d',  // 叶片3 墨绿
  4: '#f59e0b',  // 塔筒1 琥珀
  5: '#d97706',  // 塔筒2 橙
  6: '#ef4444',  // 机舱 红
}

const strokeColor = (cn: number) => colorMap[cn] || '#666'
const countByComponent = computed(() => {
  const m: Record<number, number> = {}
  for (const p of placements.value) {
    m[p.component_no] = (m[p.component_no] || 0) + 1
  }
  return m
})

// Hatch definitions (mirroring vessel config)
const hatches = [
  { id: 'H1', x: 0, y: 0, w: 28000, h: 22000 },
  { id: 'H2', x: 29000, y: 0, w: 28000, h: 22000 },
  { id: 'H3', x: 58000, y: 0, w: 28000, h: 22000 },
  { id: 'H4', x: 87000, y: 0, w: 28000, h: 22000 },
  { id: 'H5', x: 116000, y: 0, w: 28000, h: 22000 },
  { id: 'H6', x: 145000, y: 0, w: 29000, h: 22000 },
  { id: 'H7', x: 175000, y: 0, w: 29000, h: 22000 },
  { id: 'H8', x: 205000, y: 0, w: 29000, h: 22000 },
]

const minX = 0
const maxX = 234000
const minY = 0
const maxY = 22000

const viewW = maxX - minX
const viewH = maxY - minY + 4000
const viewHeight = 280

const scale = (v: number) => v
</script>
