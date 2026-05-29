<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import type { MemoryMergeResponse } from '@/types'
import { useI18n } from '@/i18n'

defineProps<{
  open: boolean
  loading: boolean
  preview: MemoryMergeResponse | null
  selectedCount: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'preview'): void
  (e: 'confirm'): void
}>()

const { t } = useI18n()
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    :title="t('memory.mergePreviewTitle')"
    :description="t('memory.mergePreviewDescription', { count: selectedCount })"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <section class="rounded-2xl border border-amber-100/10 bg-surface-0 p-4">
        <p class="text-sm leading-6 text-stone-300">
          {{ t('memory.mergePreviewHint') }}
        </p>
      </section>

      <section
        v-if="preview"
        class="rounded-2xl border border-amber-100/10 bg-surface-0 p-4"
      >
        <div class="flex flex-wrap items-center gap-3 text-xs text-stone-400">
          <span>{{ t('memory.targetType', { value: preview.memory_type }) }}</span>
          <span>{{ t('memory.importance') }}: {{ Math.round(preview.importance * 100) }}%</span>
        </div>
        <pre class="mt-4 whitespace-pre-wrap rounded-2xl border border-amber-100/10 bg-[#0d0b09] p-4 text-sm leading-6 text-stone-100">{{ preview.merged_content }}</pre>
      </section>
    </div>

    <template #footer>
      <div class="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
          @click="emit('close')"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-amber-500/10 px-4 py-2 text-stone-100 transition-colors hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
          @click="emit('preview')"
        >
          {{ loading ? t('memory.loading') : (preview ? t('memory.regeneratePreview') : t('memory.generatePreview')) }}
        </button>
        <button
          v-if="preview"
          type="button"
          class="rounded-2xl bg-amber-400 px-4 py-2 font-medium text-stone-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-stone-600 disabled:text-stone-300"
          :disabled="loading"
          @click="emit('confirm')"
        >
          {{ t('memory.replaceOriginal') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
