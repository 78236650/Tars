<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import type { MemoryCompressionStatus } from '@/types'
import { useI18n } from '@/i18n'

defineProps<{
  open: boolean
  status: MemoryCompressionStatus | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useI18n()
const getProgressNumber = (progress: Record<string, unknown>, key: string) => {
  const value = progress[key]
  return typeof value === 'number' ? value : 0
}
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    :title="t('memory.compressDialogTitle')"
    :description="t('memory.compressDialogDescription')"
    size="lg"
    @close="emit('close')"
  >
    <div v-if="status" class="space-y-4">
      <section class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <div class="flex items-center justify-between text-sm">
          <span class="text-stone-400">{{ t('memory.currentStatus') }}</span>
          <span class="font-medium text-stone-100">{{ status.status }}</span>
        </div>
        <div class="mt-2 flex items-center justify-between gap-4 text-xs text-stone-400">
          <span>{{ t('memory.startedAt', { value: status.last_started_at || t('memory.none') }) }}</span>
          <span>{{ t('memory.finishedAt', { value: status.last_finished_at || t('memory.inProgress') }) }}</span>
        </div>
      </section>

      <section v-if="status.progress" class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <p class="text-sm text-stone-100">{{ t('memory.progressTitle') }}</p>
        <p class="mt-2 text-sm text-stone-400">
          {{ t('memory.progressSummary', { done: getProgressNumber(status.progress, 'entities_done'), total: getProgressNumber(status.progress, 'entities_total') }) }}
        </p>
      </section>

      <section v-if="status.last_report" class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <p class="text-sm text-stone-100">{{ t('memory.reportTitle') }}</p>
        <div class="mt-3 grid gap-3 text-sm text-stone-300 md:grid-cols-2">
          <div class="rounded-2xl border border-amber-100/10 bg-[#0d0b09] px-3 py-3">
            {{ t('memory.reportCompressedCount', { count: status.last_report.compressed_count ?? 0 }) }}
          </div>
          <div class="rounded-2xl border border-amber-100/10 bg-[#0d0b09] px-3 py-3">
            {{ t('memory.reportCleanedCount', { count: status.last_report.cleaned_count ?? 0 }) }}
          </div>
        </div>
        <p v-if="status.last_report.error" class="mt-3 text-sm text-red-300">
          {{ t('memory.errorLabel', { error: status.last_report.error }) }}
        </p>
      </section>
    </div>

    <div v-else class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4 text-sm text-stone-400">
      {{ t('memory.noCompressStatus') }}
    </div>

    <template #footer>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
          @click="emit('close')"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
