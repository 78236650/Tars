<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import type { MemoryCompressionStatus } from '@/types'

defineProps<{
  open: boolean
  status: MemoryCompressionStatus | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    title="记忆压缩进度"
    description="查看当前压缩任务状态、处理进度与最近一次报告。"
    size="lg"
    @close="emit('close')"
  >
    <div v-if="status" class="space-y-4">
      <section class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <div class="flex items-center justify-between text-sm">
          <span class="text-stone-400">当前状态</span>
          <span class="font-medium text-stone-100">{{ status.status }}</span>
        </div>
        <div class="mt-2 flex items-center justify-between gap-4 text-xs text-stone-400">
          <span>开始时间：{{ status.last_started_at || '暂无' }}</span>
          <span>结束时间：{{ status.last_finished_at || '进行中' }}</span>
        </div>
      </section>

      <section v-if="status.progress" class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <p class="text-sm text-stone-100">处理进度</p>
        <p class="mt-2 text-sm text-stone-400">
          已完成 {{ status.progress.entities_done || 0 }} / {{ status.progress.entities_total || 0 }} 个实体压缩任务
        </p>
      </section>

      <section v-if="status.last_report" class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
        <p class="text-sm text-stone-100">压缩报告</p>
        <div class="mt-3 grid gap-3 text-sm text-stone-300 md:grid-cols-2">
          <div class="rounded-2xl border border-amber-100/10 bg-[#0d0b09] px-3 py-3">
            压缩批次：{{ status.last_report.compressed_count ?? 0 }}
          </div>
          <div class="rounded-2xl border border-amber-100/10 bg-[#0d0b09] px-3 py-3">
            清理条数：{{ status.last_report.cleaned_count ?? 0 }}
          </div>
        </div>
        <p v-if="status.last_report.error" class="mt-3 text-sm text-red-300">
          错误：{{ status.last_report.error }}
        </p>
      </section>
    </div>

    <div v-else class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4 text-sm text-stone-400">
      暂无压缩状态
    </div>

    <template #footer>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
          @click="emit('close')"
        >
          关闭
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
