<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from '@/i18n'
import type { InsightMetricAnswer } from '@/api'
import { insightApi } from '@/api'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  answer: InsightMetricAnswer
  datasourceId: string
  sessionId?: string
}>()

const emit = defineEmits<{
  clarify: [payload: { question: string; candidate_metric_keys: string[] }]
}>()

const { t } = useI18n()
const toast = useToast()
const sqlOpen = ref(false)
const reasoningOpen = ref(false)
const loading = ref(false)

const tierLabel = computed(() => {
  const map: Record<string, string> = {
    official: t('insight.tier.official'),
    suggested: t('insight.tier.suggested'),
    adhoc: t('insight.tier.adhoc'),
  }
  return map[props.answer.caliber_tier] || props.answer.caliber_tier
})

const tierClass = computed(() => {
  if (props.answer.caliber_tier === 'official') return 'bg-emerald-900/40 text-emerald-300'
  if (props.answer.caliber_tier === 'suggested') return 'bg-amber-900/40 text-amber-300'
  return 'bg-slate-700 text-slate-300'
})

const formatValue = computed(() => {
  if (props.answer.value === null || props.answer.value === undefined) return '—'
  const u = props.answer.unit ? ` ${props.answer.unit}` : ''
  return `${props.answer.value}${u}`
})

const freshness = computed(() => {
  if (props.answer.as_of) return t('insight.metric.asOf', { date: props.answer.as_of })
  if (props.answer.lag_seconds != null) return t('insight.metric.lag', { sec: props.answer.lag_seconds })
  return ''
})

const copySql = async () => {
  try {
    await navigator.clipboard.writeText(props.answer.sql || '')
    toast.success(t('insight.metric.copiedSql'))
  } catch {
    toast.error(t('insight.metric.copyFailed'))
  }
}

const pickCandidate = (key: string) => {
  emit('clarify', {
    question: t('insight.metric.clarifyDefault'),
    candidate_metric_keys: [key],
  })
}

const onFeedback = async (score: number) => {
  if (!props.answer.question_log_id) return
  loading.value = true
  try {
    await insightApi.feedback(props.answer.question_log_id, score)
    toast.success(t('insight.metric.feedbackThanks'))
  } catch {
    toast.error(t('insight.metric.feedbackFailed'))
  } finally {
    loading.value = false
  }
}

const canAdopt = computed(
  () =>
  props.answer.caliber_tier !== 'official' &&
  (props.answer.metric_id || props.answer.question_log_id)
)

const onAdopt = async () => {
  if (!props.answer.metric_id && !props.answer.question_log_id) return
  loading.value = true
  try {
    await insightApi.adoptMetric({
      metric_id: props.answer.metric_id,
      question_log_id: props.answer.question_log_id,
    })
    toast.success(t('insight.metric.adoptSuccess'))
  } catch {
    toast.error(t('insight.metric.adoptFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="metric-answer-card rounded-lg border border-stone-700/80 bg-stone-900/60 p-4 text-sm">
    <div class="flex items-start justify-between gap-2 mb-3">
      <div>
        <div class="text-xs text-stone-500 mb-1">{{ t('insight.metric.result') }}</div>
        <div class="text-2xl font-semibold text-stone-100">{{ formatValue }}</div>
        <div v-if="freshness" class="text-xs text-stone-500 mt-1">{{ freshness }}</div>
      </div>
      <span class="text-xs px-2 py-0.5 rounded shrink-0" :class="tierClass">{{ tierLabel }}</span>
    </div>

    <div class="mb-3">
      <div class="text-xs text-stone-500 mb-1">{{ t('insight.metric.caliber') }}</div>
      <p class="text-stone-300 leading-relaxed">{{ answer.definition || '—' }}</p>
      <p v-if="answer.metric_key" class="text-xs text-stone-500 mt-1 font-mono">{{ answer.metric_key }}</p>
      <p class="text-xs text-stone-500 mt-1">
        {{ t('insight.metric.confidence') }}: {{ Math.round((answer.confidence || 0) * 100) }}%
        · {{ answer.branch }}
      </p>
    </div>

    <div v-if="answer.branch === 'hit_partial' && answer.candidates?.length" class="mb-3">
      <div class="text-xs text-stone-500 mb-2">{{ t('insight.metric.pickCandidate') }}</div>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="key in answer.candidates"
          :key="key"
          type="button"
          class="px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs"
          @click="pickCandidate(key)"
        >
          {{ key }}
        </button>
      </div>
      <ul v-if="answer.open_questions?.length" class="mt-2 text-xs text-amber-300/90 list-disc pl-4">
        <li v-for="(q, i) in answer.open_questions" :key="i">{{ q }}</li>
      </ul>
    </div>

    <div v-if="answer.error" class="mb-3 text-xs text-red-400">
      {{ answer.error.message }} ({{ answer.error.code }})
    </div>

    <div class="mb-3">
      <button type="button" class="text-xs text-stone-400 hover:text-stone-200" @click="sqlOpen = !sqlOpen">
        {{ sqlOpen ? '▼' : '▶' }} SQL
      </button>
      <pre v-if="sqlOpen" class="mt-2 p-2 rounded bg-stone-950 text-xs text-stone-300 overflow-x-auto">{{ answer.sql }}</pre>
    </div>

    <div v-if="answer.filters_summary || answer.reasoning" class="mb-3 text-xs text-stone-500">
      <div v-if="answer.filters_summary">{{ answer.filters_summary }}</div>
      <button
        v-if="answer.reasoning"
        type="button"
        class="mt-1 text-stone-400 hover:text-stone-200"
        @click="reasoningOpen = !reasoningOpen"
      >
        {{ reasoningOpen ? t('insight.metric.hideReasoning') : t('insight.metric.showReasoning') }}
      </button>
      <p v-if="reasoningOpen" class="mt-1 text-stone-400">{{ answer.reasoning }}</p>
    </div>

    <div class="flex flex-wrap gap-2 pt-2 border-t border-stone-800">
      <button type="button" class="btn-sm" @click="copySql">{{ t('insight.metric.copySql') }}</button>
      <button type="button" class="btn-sm" :disabled="loading" @click="onFeedback(1)">👍</button>
      <button type="button" class="btn-sm" :disabled="loading" @click="onFeedback(-1)">👎</button>
      <button
        v-if="canAdopt"
        type="button"
        class="btn-sm text-emerald-300"
        :disabled="loading"
        @click="onAdopt"
      >
        {{ t('insight.metric.adopt') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.btn-sm {
  @apply px-2 py-1 rounded text-xs bg-stone-800 hover:bg-stone-700 text-stone-200 disabled:opacity-50;
}
</style>
