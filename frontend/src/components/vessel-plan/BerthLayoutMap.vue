<script setup lang="ts">
import type { VpBerth, VpHorizonRow } from '@/types'

const props = defineProps<{
  berths: VpBerth[]
  rows: VpHorizonRow[]
  highlightBerthId?: string | null
}>()

const emit = defineEmits<{
  'berth-select': [berthId: string]
}>()

const occupancy = (berthId: string) => {
  const row = props.rows.find((r) => r.berth_id === berthId)
  return row?.vessel_name ?? null
}

const zoneColor = (zone: string) => {
  if (zone === 'A') return 'border-sky-500/40 bg-sky-500/10'
  if (zone === 'B') return 'border-emerald-500/40 bg-emerald-500/10'
  return 'border-amber-500/40 bg-amber-500/10'
}
</script>

<template>
  <div class="rounded-xl border border-border bg-surface-1 p-4">
    <p class="mb-3 text-xs font-medium text-content-muted">泊位平面（当前占用）</p>
    <div class="flex flex-wrap gap-3">
      <button
        v-for="b in berths"
        :key="b.id"
        type="button"
        class="min-w-[100px] rounded-lg border px-3 py-2 text-left transition hover:ring-1 hover:ring-accent/40"
        :class="[
          zoneColor(b.yard_zone),
          highlightBerthId === b.id ? 'ring-2 ring-accent' : '',
        ]"
        @click="emit('berth-select', b.id)"
      >
        <p class="text-sm font-medium text-content">{{ b.name }}</p>
        <p class="mt-1 truncate text-xs text-content-muted">
          {{ occupancy(b.id) || '空闲' }}
        </p>
        <p class="text-[10px] text-content-muted">堆场 {{ b.yard_zone }}</p>
      </button>
    </div>
  </div>
</template>
