<script setup lang="ts">
import { ref } from 'vue'
import { orchestrationApi } from '@/api'
import type { OrchestrationDispatchResult } from '@/types'
import type { DispatchMode } from './orchestration-meta'
import OrchestrationWorkflowSteps from './OrchestrationWorkflowSteps.vue'
import OrchestrationScenarioCards from './OrchestrationScenarioCards.vue'
import OrchestrationGuidedForm from './OrchestrationGuidedForm.vue'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { useChatStore } from '@/stores/chat'

const emit = defineEmits<{
  dispatched: [result: OrchestrationDispatchResult]
  'step-change': [step: 1 | 2 | 3]
}>()

const { t } = useI18n()
const toast = useToast()
const chatStore = useChatStore()

const mode = ref<DispatchMode>('scenario')
const goal = ref('')
const dispatching = ref(false)
const activeStep = ref<1 | 2 | 3>(1)

const modes: { id: DispatchMode; labelKey: string }[] = [
  { id: 'scenario', labelKey: 'orchestration.mode.scenario' },
  { id: 'guided', labelKey: 'orchestration.mode.guided' },
  { id: 'advanced', labelKey: 'orchestration.mode.advanced' },
]

async function dispatchWithGoal(text: string) {
  const trimmed = text.trim()
  if (!trimmed || dispatching.value) return
  dispatching.value = true
  activeStep.value = 2
  emit('step-change', 2)
  try {
    const sessionId = chatStore.currentSessionId || 'default-session'
    const result = await orchestrationApi.dispatch(sessionId, trimmed)
    toast.success(t('orchestration.dispatchSuccess'))
    goal.value = ''
    activeStep.value = 3
    emit('step-change', 3)
    emit('dispatched', result)
  } catch (e) {
    console.error(e)
    toast.error(t('orchestration.dispatchFailed'))
    activeStep.value = 1
    emit('step-change', 1)
  } finally {
    dispatching.value = false
  }
}

function onScenarioSelect(g: string) {
  void dispatchWithGoal(g)
}

function onGuidedSubmit(g: string) {
  void dispatchWithGoal(g)
}

function onAdvancedSubmit() {
  void dispatchWithGoal(goal.value)
}

function switchMode(id: DispatchMode) {
  mode.value = id
  activeStep.value = 1
  emit('step-change', 1)
}
</script>

<template>
  <section class="rounded-2xl border border-border bg-surface-2/80 p-5 md:p-6">
    <div class="mb-5">
      <h2 class="text-lg font-semibold text-content">{{ t('orchestration.dispatchTitle') }}</h2>
      <p class="mt-1 text-sm text-content-muted">{{ t('orchestration.dispatchHintBiz') }}</p>
    </div>

    <OrchestrationWorkflowSteps :active-step="activeStep" class="mb-6" />

    <div
      class="mb-5 flex flex-wrap gap-2 rounded-xl border border-border bg-surface-1 p-1"
      role="tablist"
      :aria-label="t('orchestration.mode.label')"
    >
      <button
        v-for="m in modes"
        :key="m.id"
        type="button"
        role="tab"
        class="flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition min-w-[7rem]"
        :class="
          mode === m.id
            ? 'bg-accent text-white shadow-sm'
            : 'text-content-muted hover:bg-surface-2 hover:text-content'
        "
        :aria-selected="mode === m.id"
        @click="switchMode(m.id)"
      >
        {{ t(m.labelKey) }}
      </button>
    </div>

    <div v-if="dispatching" class="mb-4 flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-content">
      <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      {{ t('orchestration.dispatchingDetail') }}
    </div>

    <OrchestrationScenarioCards
      v-if="mode === 'scenario' && !dispatching"
      @select="onScenarioSelect"
    />

    <OrchestrationGuidedForm
      v-else-if="mode === 'guided' && !dispatching"
      @submit="onGuidedSubmit"
    />

    <div v-else-if="mode === 'advanced' && !dispatching" class="space-y-3">
      <p class="text-xs text-content-muted">{{ t('orchestration.advanced.note') }}</p>
      <textarea
        v-model="goal"
        class="w-full resize-none rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content placeholder:text-content-muted focus:border-accent focus:outline-none"
        rows="4"
        :placeholder="t('orchestration.dispatchPlaceholder')"
      />
      <button
        type="button"
        class="rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        :disabled="!goal.trim()"
        @click="onAdvancedSubmit"
      >
        {{ t('orchestration.dispatchSubmit') }}
      </button>
    </div>
  </section>
</template>
