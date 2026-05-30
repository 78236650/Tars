<script setup lang="ts">
import { nextTick, ref } from 'vue'
import OrchestrationTaskView from '@/components/orchestration/OrchestrationTaskView.vue'
import VesselPlanTab from '@/components/vessel-plan/VesselPlanTab.vue'
import { useI18n } from '@/i18n'

const { t } = useI18n()
const tab = ref<'ops' | 'plan'>('ops')
const opsRef = ref<InstanceType<typeof OrchestrationTaskView> | null>(null)

async function onAdopted(taskId: string) {
  tab.value = 'ops'
  await nextTick()
  await opsRef.value?.loadTasks()
  await opsRef.value?.openDetail(taskId)
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div class="flex shrink-0 gap-1 border-b border-border px-4 pt-3">
      <button
        type="button"
        class="rounded-t-lg px-4 py-2 text-sm font-medium transition"
        :class="
          tab === 'ops'
            ? 'border border-b-0 border-border bg-surface-1 text-content'
            : 'text-content-muted hover:text-content'
        "
        @click="tab = 'ops'"
      >
        {{ t('orchestration.tab.ops') }}
      </button>
      <button
        type="button"
        class="rounded-t-lg px-4 py-2 text-sm font-medium transition"
        :class="
          tab === 'plan'
            ? 'border border-b-0 border-border bg-surface-1 text-content'
            : 'text-content-muted hover:text-content'
        "
        @click="tab = 'plan'"
      >
        {{ t('orchestration.tab.plan') }}
      </button>
    </div>
    <div class="min-h-0 flex-1 overflow-hidden">
      <OrchestrationTaskView v-show="tab === 'ops'" ref="opsRef" class="h-full" />
      <VesselPlanTab v-show="tab === 'plan'" class="h-full" @adopted="onAdopted" />
    </div>
  </div>
</template>
