<script setup lang="ts">
import { ref } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { SCENARIO_TEMPLATES, fillScenarioGoal } from './orchestration-meta'
import { useI18n } from '@/i18n'

const emit = defineEmits<{
  select: [goal: string]
}>()

const { t } = useI18n()
const selectedId = ref<string | null>(null)
const ship = ref('')
const boxes = ref('800')

function pick(id: string) {
  selectedId.value = id
}

function confirm() {
  const scenario = SCENARIO_TEMPLATES.find((s) => s.id === selectedId.value)
  if (!scenario || !ship.value.trim()) return
  emit(
    'select',
    fillScenarioGoal(scenario.goalTemplate, {
      ship: ship.value,
      boxes: boxes.value,
    }),
  )
  selectedId.value = null
}
</script>

<template>
  <div class="space-y-4">
    <p class="text-sm text-content-muted">{{ t('orchestration.scenario.intro') }}</p>

    <div class="grid gap-3 sm:grid-cols-3">
      <button
        v-for="item in SCENARIO_TEMPLATES"
        :key="item.id"
        type="button"
        class="flex flex-col items-start gap-3 rounded-xl border p-4 text-left transition"
        :class="
          selectedId === item.id
            ? 'border-accent bg-accent/10 ring-1 ring-accent/40'
            : 'border-border bg-surface-1 hover:border-accent/30 hover:bg-surface-2'
        "
        @click="pick(item.id)"
      >
        <span
          class="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface-2"
        >
          <BaseIcon :icon="item.icon" :size="22" class="text-accent" />
        </span>
        <div>
          <p class="font-medium text-content">
            {{ t(`orchestration.scenario.${item.id}.title`) }}
          </p>
          <p class="mt-1 text-xs leading-relaxed text-content-muted">
            {{ t(`orchestration.scenario.${item.id}.desc`) }}
          </p>
        </div>
      </button>
    </div>

    <div
      v-if="selectedId"
      class="rounded-xl border border-accent/30 bg-surface-2 p-4 space-y-3"
    >
      <p class="text-sm font-medium text-content">{{ t('orchestration.scenario.fillShip') }}</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mb-1 block text-xs text-content-muted">{{
            t('orchestration.field.ship')
          }}</span>
          <input
            v-model="ship"
            type="text"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content"
            :placeholder="t('orchestration.field.shipPh')"
          />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs text-content-muted">{{
            t('orchestration.field.boxes')
          }}</span>
          <input
            v-model="boxes"
            type="text"
            inputmode="numeric"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content"
            placeholder="800"
          />
        </label>
      </div>
      <button
        type="button"
        class="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        :disabled="!ship.trim()"
        @click="confirm"
      >
        {{ t('orchestration.scenario.run') }}
      </button>
    </div>
  </div>
</template>
