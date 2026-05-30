<script setup lang="ts">
import { reactive } from 'vue'
import { buildGuidedGoal } from './orchestration-meta'
import { useI18n } from '@/i18n'

const emit = defineEmits<{
  submit: [goal: string]
}>()

const { t } = useI18n()

const form = reactive({
  ship: '',
  boxes: '',
  berth: '',
  eta: '',
  jobType: 'unload' as 'unload' | 'load' | 'both',
})

function onSubmit() {
  if (!form.ship.trim()) return
  emit('submit', buildGuidedGoal(form))
}
</script>

<template>
  <form class="space-y-4" @submit.prevent="onSubmit">
    <p class="text-sm text-content-muted">{{ t('orchestration.guided.intro') }}</p>

    <div class="grid gap-4 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mb-1 block text-sm font-medium text-content">{{
          t('orchestration.field.ship')
        }}</span>
        <input
          v-model="form.ship"
          required
          type="text"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-sm text-content"
          :placeholder="t('orchestration.field.shipPh')"
        />
      </label>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-content">{{
          t('orchestration.field.jobType')
        }}</span>
        <select
          v-model="form.jobType"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-sm text-content"
        >
          <option value="unload">{{ t('orchestration.job.unload') }}</option>
          <option value="load">{{ t('orchestration.job.load') }}</option>
          <option value="both">{{ t('orchestration.job.both') }}</option>
        </select>
      </label>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-content">{{
          t('orchestration.field.boxes')
        }}</span>
        <input
          v-model="form.boxes"
          type="text"
          inputmode="numeric"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-sm text-content"
          :placeholder="t('orchestration.field.boxesPh')"
        />
      </label>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-content">{{
          t('orchestration.field.berth')
        }}</span>
        <input
          v-model="form.berth"
          type="text"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-sm text-content"
          :placeholder="t('orchestration.field.berthPh')"
        />
      </label>

      <label class="block">
        <span class="mb-1 block text-sm font-medium text-content">{{
          t('orchestration.field.eta')
        }}</span>
        <input
          v-model="form.eta"
          type="text"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2.5 text-sm text-content"
          :placeholder="t('orchestration.field.etaPh')"
        />
      </label>
    </div>

    <button
      type="submit"
      class="w-full rounded-lg bg-accent py-3 text-sm font-semibold text-white disabled:opacity-50 sm:w-auto sm:px-8"
      :disabled="!form.ship.trim()"
    >
      {{ t('orchestration.guided.submit') }}
    </button>
  </form>
</template>
