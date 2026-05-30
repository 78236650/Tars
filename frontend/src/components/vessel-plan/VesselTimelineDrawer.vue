<script setup lang="ts">
import { ref, watch } from 'vue'
import type { VpBerth, VpVoyageDetail } from '@/types'
import { vesselPlanApi } from '@/api'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import BaseIcon from '@/components/common/BaseIcon.vue'

const props = defineProps<{
  open: boolean
  voyageId: string | null
  berths: VpBerth[]
}>()

const emit = defineEmits<{
  close: []
  updated: []
}>()

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const detail = ref<VpVoyageDetail | null>(null)
const berthId = ref('')
const locked = ref(false)
const saving = ref(false)

watch(
  () => [props.open, props.voyageId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null
      return
    }
    loading.value = true
    try {
      detail.value = await vesselPlanApi.getVoyage(id)
      berthId.value = detail.value.assignment?.berth_id ?? ''
      locked.value = detail.value.assignment?.locked ?? false
    } catch (e) {
      console.error(e)
      toast.error(t('vesselPlan.loadFailed'))
      emit('close')
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function savePatch() {
  if (!props.voyageId) return
  saving.value = true
  try {
    await vesselPlanApi.patchAssignment(props.voyageId, {
      berth_id: berthId.value || undefined,
      locked: locked.value,
    })
    toast.success(t('vesselPlan.saved'))
    emit('updated')
    detail.value = await vesselPlanApi.getVoyage(props.voyageId)
  } catch (e) {
    console.error(e)
    toast.error(t('common.error'))
  } finally {
    saving.value = false
  }
}

function formatTime(value: string) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <aside class="flex h-full w-full max-w-md flex-col border-l border-border bg-surface-1 shadow-2xl">
        <header class="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 class="text-lg font-semibold text-content">{{ t('vesselPlan.drawerTitle') }}</h2>
          <button type="button" class="rounded-lg p-2 text-content-muted hover:bg-surface-2" @click="emit('close')">
            <BaseIcon icon="lucide:x" :size="20" />
          </button>
        </header>
        <div v-if="loading" class="p-6 text-sm text-content-muted">{{ t('common.loading') }}</div>
        <div v-else-if="detail" class="flex-1 space-y-5 overflow-y-auto p-5">
          <section>
            <h3 class="text-base font-semibold text-content">{{ detail.voyage.vessel_name }}</h3>
            <p class="text-xs text-content-muted">
              {{ t('vesselPlan.field.boxes') }}: {{ detail.voyage.cargo_teu }} ·
              {{ t('orchestration.field.berth') }}区 {{ detail.voyage.target_yard_zone }}
            </p>
          </section>
          <section>
            <h4 class="mb-2 text-sm font-medium text-content">{{ t('vesselPlan.timeline') }}</h4>
            <ol class="space-y-3 border-l-2 border-accent/30 pl-4">
              <li v-for="(item, i) in detail.timeline" :key="i">
                <p class="text-xs font-medium text-accent">{{ item.stage }}</p>
                <p class="text-sm text-content">{{ formatTime(item.time) }}</p>
                <p class="text-xs text-content-muted">{{ item.detail }}</p>
              </li>
            </ol>
          </section>
          <section v-if="detail.alternatives.length" class="rounded-lg border border-border bg-surface-2 p-3">
            <p class="text-xs font-medium text-content-muted">{{ t('vesselPlan.alternatives') }}</p>
            <p class="mt-1 text-sm text-content">{{ detail.alternatives.join('、') }}</p>
          </section>
          <section class="space-y-3 rounded-xl border border-border p-4">
            <h4 class="text-sm font-medium text-content">{{ t('vesselPlan.adjust') }}</h4>
            <label class="block text-xs text-content-muted">
              {{ t('orchestration.field.berth') }}
              <select
                v-model="berthId"
                class="mt-1 w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content"
              >
                <option value="">{{ t('vesselPlan.berthAuto') }}</option>
                <option v-for="b in berths" :key="b.id" :value="b.id">{{ b.name }}</option>
              </select>
            </label>
            <label class="flex items-center gap-2 text-sm text-content">
              <input v-model="locked" type="checkbox" class="rounded" />
              {{ t('vesselPlan.lockPlan') }}
            </label>
            <button
              type="button"
              class="w-full rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface-1 disabled:opacity-50"
              :disabled="saving"
              @click="savePatch"
            >
              {{ t('common.save') }}
            </button>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
