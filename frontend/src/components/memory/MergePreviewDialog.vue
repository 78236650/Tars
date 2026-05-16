<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import type { MemoryMergeResponse } from '@/types'

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
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    title="合并压缩预览"
    :description="`已选择 ${selectedCount} 条长期记忆`"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <section class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <p class="text-sm leading-6 text-stone-300">
          点击“生成预览”后，将调用后端合并接口生成摘要；确认后会替换原始记忆。
        </p>
      </section>

      <section
        v-if="preview"
        class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4"
      >
        <div class="flex flex-wrap items-center gap-3 text-xs text-stone-400">
          <span>目标类型：{{ preview.memory_type }}</span>
          <span>Importance：{{ Math.round(preview.importance * 100) }}%</span>
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
          取消
        </button>
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-amber-500/10 px-4 py-2 text-stone-100 transition-colors hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
          @click="emit('preview')"
        >
          {{ loading ? '生成中...' : (preview ? '重新生成预览' : '生成预览') }}
        </button>
        <button
          v-if="preview"
          type="button"
          class="rounded-2xl bg-amber-400 px-4 py-2 font-medium text-stone-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-stone-600 disabled:text-stone-300"
          :disabled="loading"
          @click="emit('confirm')"
        >
          确认替换原记忆
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
