<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { vesselPlanApi } from '@/api'
import type { VpHorizonResponse } from '@/types'
import BerthGanttChart from './BerthGanttChart.vue'
import BerthLayoutMap from './BerthLayoutMap.vue'
import VesselTimelineDrawer from './VesselTimelineDrawer.vue'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{
  adopted: [taskId: string]
}>()

const { t } = useI18n()
const toast = useToast()
const chatStore = useChatStore()
const authStore = useAuthStore()

const loading = ref(false)
const optimizing = ref(false)
const data = ref<VpHorizonResponse | null>(null)
const selectedVoyageId = ref<string | null>(null)
const highlightBerthId = ref<string | null>(null)
const drawerOpen = ref(false)
const selectedIds = ref<string[]>([])

const horizonHours = 48

async function loadHorizon() {
  loading.value = true
  try {
    data.value = await vesselPlanApi.getHorizon(horizonHours)
  } catch (e) {
    console.error(e)
    toast.error(t('vesselPlan.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function runOptimize() {
  optimizing.value = true
  try {
    data.value = await vesselPlanApi.optimize(horizonHours)
    toast.success(t('vesselPlan.optimizeDone'))
  } catch (e) {
    console.error(e)
    toast.error(t('common.error'))
  } finally {
    optimizing.value = false
  }
}

async function runRecompute() {
  optimizing.value = true
  try {
    data.value = await vesselPlanApi.recompute(horizonHours)
    toast.success(t('vesselPlan.recomputeDone'))
  } catch (e) {
    console.error(e)
    toast.error(t('common.error'))
  } finally {
    optimizing.value = false
  }
}

function toggleSelect(voyageId: string) {
  const idx = selectedIds.value.indexOf(voyageId)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(voyageId)
}

function openVoyage(voyageId: string) {
  selectedVoyageId.value = voyageId
  drawerOpen.value = true
}

function onBerthSelect(berthId: string) {
  highlightBerthId.value = berthId
  const row = data.value?.rows.find((r) => r.berth_id === berthId)
  if (row) openVoyage(row.voyage_id)
}

async function confirmAdopt() {
  if (!selectedIds.value.length) return
  try {
    const sessionId = chatStore.currentSessionId || 'default-session'
    const res = await vesselPlanApi.adopt(selectedIds.value, sessionId)
    toast.success(t('vesselPlan.adoptSuccess', { n: String(res.count) }))
    selectedIds.value = []
    await loadHorizon()
    if (res.task_ids[0]) emit('adopted', res.task_ids[0])
  } catch (e) {
    console.error(e)
    toast.error(t('common.error'))
  }
}

async function resetDemo() {
  if (!authStore.user?.role || authStore.user.role !== 'admin') {
    toast.error(t('vesselPlan.adminOnly'))
    return
  }
  try {
    await vesselPlanApi.resetDemo()
    await loadHorizon()
    toast.success(t('vesselPlan.resetDone'))
  } catch (e) {
    console.error(e)
    toast.error(t('common.error'))
  }
}

const adoptLabel = computed(() =>
  t('vesselPlan.adopt', { n: String(selectedIds.value.length) }),
)

onMounted(() => {
  void loadHorizon()
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4 md:p-6">
    <div class="flex flex-wrap items-center gap-2">
      <span class="rounded-full bg-surface-2 px-3 py-1 text-xs text-content-muted">
        {{ t('vesselPlan.horizon', { h: String(horizonHours) }) }}
      </span>
      <button
        type="button"
        class="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-surface-1 disabled:opacity-50"
        :disabled="optimizing"
        @click="runOptimize"
      >
        {{ optimizing ? t('vesselPlan.optimizing') : t('vesselPlan.optimize') }}
      </button>
      <button
        type="button"
        class="rounded-lg border border-border px-3 py-1.5 text-sm text-content hover:bg-surface-2 disabled:opacity-50"
        :disabled="optimizing"
        @click="runRecompute"
      >
        {{ t('vesselPlan.recompute') }}
      </button>
      <button
        type="button"
        class="rounded-lg border border-accent/50 bg-accent/10 px-3 py-1.5 text-sm text-content disabled:opacity-40"
        :disabled="!selectedIds.length"
        @click="confirmAdopt"
      >
        {{ adoptLabel }}
      </button>
      <button
        v-if="authStore.user?.role === 'admin'"
        type="button"
        class="rounded-lg border border-border px-3 py-1.5 text-xs text-content-muted hover:bg-surface-2"
        @click="resetDemo"
      >
        {{ t('vesselPlan.resetDemo') }}
      </button>
    </div>

    <div
      v-if="data?.agent_summary"
      class="rounded-xl border border-border bg-surface-2/80 px-4 py-3 text-sm text-content"
    >
      {{ data.agent_summary }}
      <p v-if="data.warnings?.length" class="mt-2 text-xs text-amber-300">
        {{ data.warnings.slice(0, 3).join('；') }}
      </p>
    </div>

    <div v-if="loading" class="text-sm text-content-muted">{{ t('common.loading') }}</div>

    <template v-else-if="data">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <BerthGanttChart
          :berths="data.berths"
          :rows="data.rows"
          :horizon-hours="horizonHours"
          :selected-voyage-id="selectedVoyageId"
          @select="openVoyage"
        />
        <div class="overflow-hidden rounded-xl border border-border">
          <table class="w-full text-sm">
            <thead class="border-b border-border bg-surface-2 text-left text-xs text-content-muted">
              <tr>
                <th class="p-2 w-8"></th>
                <th class="p-2">{{ t('vesselPlan.col.ship') }}</th>
                <th class="p-2">{{ t('vesselPlan.col.berth') }}</th>
                <th class="p-2">{{ t('vesselPlan.col.wait') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in data.rows"
                :key="row.voyage_id"
                class="cursor-pointer border-b border-border/50 hover:bg-surface-2/60"
                :class="selectedVoyageId === row.voyage_id ? 'bg-accent/10' : ''"
                @click="openVoyage(row.voyage_id)"
              >
                <td class="p-2" @click.stop="toggleSelect(row.voyage_id)">
                  <input type="checkbox" :checked="selectedIds.includes(row.voyage_id)" />
                </td>
                <td class="p-2 font-medium text-content">{{ row.vessel_name }}</td>
                <td class="p-2 text-content-muted">{{ row.berth_name || '—' }}</td>
                <td class="p-2 text-content-muted">{{ row.wait_min.toFixed(0) }}m</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <BerthLayoutMap
        :berths="data.berths"
        :rows="data.rows"
        :highlight-berth-id="highlightBerthId"
        @berth-select="onBerthSelect"
      />
    </template>

    <VesselTimelineDrawer
      :open="drawerOpen"
      :voyage-id="selectedVoyageId"
      :berths="data?.berths ?? []"
      @close="drawerOpen = false"
      @updated="loadHorizon"
    />
  </div>
</template>
