<script setup lang="ts">
import { computed } from 'vue'
import type { VpBerth, VpHorizonRow } from '@/types'
import { durationToWidth, timeToX } from './gantt-utils'
import { useI18n } from '@/i18n'

const props = defineProps<{
  berths: VpBerth[]
  rows: VpHorizonRow[]
  horizonHours: number
  selectedVoyageId?: string | null
}>()

const emit = defineEmits<{
  select: [voyageId: string]
}>()

const { locale } = useI18n()

const width = 720
const rowHeight = 36
const headerH = 28
const padding = 8

const nowMs = Date.now()
const endMs = nowMs + props.horizonHours * 3600 * 1000

const blocks = computed(() => {
  const items: Array<{
    voyageId: string
    label: string
    x: number
    y: number
    w: number
    waitW: number
    conflict: boolean
    selected: boolean
  }> = []

  props.berths.forEach((berth, bi) => {
    props.rows.forEach((row) => {
      if (row.berth_id !== berth.id || !row.etb || !row.etd) return
      const etaX = timeToX(row.eta, nowMs, endMs, width, padding)
      const etbX = timeToX(row.etb, nowMs, endMs, width, padding)
      const w = durationToWidth(row.etb, row.etd, nowMs, endMs, width, padding)
      items.push({
        voyageId: row.voyage_id,
        label: row.vessel_name,
        x: etbX,
        y: headerH + bi * rowHeight + 6,
        w,
        waitW: Math.max(0, etbX - etaX),
        conflict: row.wait_min > 240,
        selected: props.selectedVoyageId === row.voyage_id,
      })
    })
  })
  return items
})

const height = computed(() => headerH + props.berths.length * rowHeight + padding)
</script>

<template>
  <div class="overflow-x-auto rounded-xl border border-border bg-surface-1 p-3">
    <svg :width="width" :height="height" class="text-content">
      <text x="8" y="18" class="fill-content-muted text-[10px]">泊位 \\ 时间 →</text>
      <g v-for="(berth, i) in berths" :key="berth.id">
        <text :x="8" :y="headerH + i * rowHeight + 22" class="fill-content text-xs">
          {{ berth.name }}
        </text>
        <line
          :x1="padding"
          :y1="headerH + (i + 1) * rowHeight"
          :x2="width - padding"
          :y2="headerH + i * rowHeight"
          class="stroke-border"
        />
      </g>
      <g v-for="b in blocks" :key="b.voyageId">
        <rect
          v-if="b.waitW > 2"
          :x="b.x - b.waitW"
          :y="b.y"
          :width="b.waitW"
          :height="rowHeight - 12"
          class="fill-amber-500/20 stroke-amber-500/40"
          stroke-dasharray="4 2"
        />
        <rect
          :x="b.x"
          :y="b.y"
          :width="b.w"
          :height="rowHeight - 12"
          class="cursor-pointer transition"
          :class="
            b.selected
              ? 'fill-sky-500/40 stroke-sky-400 stroke-2'
              : b.conflict
                ? 'fill-red-500/30 stroke-red-400'
                : 'fill-emerald-500/30 stroke-emerald-500/60'
          "
          rx="4"
          @click="emit('select', b.voyageId)"
        />
        <text :x="b.x + 4" :y="b.y + 16" class="fill-content pointer-events-none text-[10px]">
          {{ b.label }}
        </text>
      </g>
    </svg>
  </div>
</template>
