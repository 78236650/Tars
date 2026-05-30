<script setup lang="ts">
import BaseIcon from '@/components/common/BaseIcon.vue'
import { useI18n } from '@/i18n'

defineProps<{
  activeStep: 1 | 2 | 3
}>()

const { t } = useI18n()

const steps = [
  { n: 1, labelKey: 'orchestration.step.choose', icon: 'lucide:layout-grid' },
  { n: 2, labelKey: 'orchestration.step.fill', icon: 'lucide:edit-3' },
  { n: 3, labelKey: 'orchestration.step.result', icon: 'lucide:clipboard-check' },
] as const
</script>

<template>
  <ol class="flex flex-wrap items-center gap-2 sm:gap-4" aria-label="作业调度步骤">
    <li
      v-for="step in steps"
      :key="step.n"
      class="flex min-w-0 flex-1 items-center gap-2"
    >
      <span
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-semibold transition-colors"
        :class="
          activeStep >= step.n
            ? 'border-accent bg-accent/20 text-accent'
            : 'border-border bg-surface-2 text-content-muted'
        "
      >
        <BaseIcon v-if="activeStep > step.n" icon="lucide:check" :size="16" />
        <BaseIcon v-else :icon="step.icon" :size="16" />
      </span>
      <span
        class="hidden truncate text-sm sm:inline"
        :class="activeStep >= step.n ? 'font-medium text-content' : 'text-content-muted'"
      >
        {{ t(step.labelKey) }}
      </span>
      <span
        v-if="step.n < 3"
        class="mx-1 hidden h-px flex-1 bg-border sm:block"
        aria-hidden="true"
      />
    </li>
  </ol>
</template>
