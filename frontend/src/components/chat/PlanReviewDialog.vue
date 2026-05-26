<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import { plansApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

export interface PendingPlanReview {
  planId: string
  sessionId: string
  goal: string
  steps: { id: number; description: string; tool: string; arguments?: Record<string, unknown> }[]
  estimatedDurationSec: number
}

const chatStore = useChatStore()
const wsStore = useWsStore()
const { t } = useI18n()
const toast = useToast()

const open = ref(false)
const pending = ref<PendingPlanReview | null>(null)
const editableSteps = ref<PendingPlanReview['steps']>([])
const submitting = ref(false)
const error = ref('')

let unsubscribe: (() => void) | null = null

const title = computed(() =>
  pending.value ? t('chat.planReview.title', { goal: pending.value.goal }) : t('chat.planReview.titleDefault'),
)

const matchesCurrentSession = (sessionId: string) => {
  const current = chatStore.currentSessionId
  return !current || !sessionId || sessionId === current
}

const showReview = (data: Record<string, unknown>) => {
  const sessionId = String(data.session_id || '')
  if (!matchesCurrentSession(sessionId)) {
    toast.info(t('chat.planReview.otherSessionToast'))
    return
  }
  const steps = Array.isArray(data.steps) ? (data.steps as PendingPlanReview['steps']) : []
  pending.value = {
    planId: String(data.plan_id || ''),
    sessionId,
    goal: String(data.goal || ''),
    steps,
    estimatedDurationSec: Number(data.estimated_duration_sec || steps.length * 30),
  }
  editableSteps.value = steps.map((s) => ({ ...s }))
  error.value = ''
  open.value = true
}

const closeDialog = () => {
  open.value = false
  pending.value = null
  editableSteps.value = []
  error.value = ''
}

const removeStep = (index: number) => {
  editableSteps.value.splice(index, 1)
}

const approvePlan = async () => {
  if (!pending.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await plansApi.approve(pending.value.planId, editableSteps.value)
    toast.success(t('chat.planReview.approved'))
    closeDialog()
  } catch {
    error.value = t('chat.planReview.actionFailed')
  } finally {
    submitting.value = false
  }
}

const rejectPlan = async () => {
  if (!pending.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await plansApi.reject(pending.value.planId)
    toast.info(t('chat.planReview.rejected'))
    closeDialog()
  } catch {
    error.value = t('chat.planReview.actionFailed')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: Record<string, unknown>) {
      if (data.type === 'plan_review_request') {
        showReview(data)
      } else if (data.type === 'plan_review_reminder') {
        toast.info(t('chat.planReview.reminder'))
      } else if (data.type === 'plan_review_cancelled') {
        if (pending.value?.planId === data.plan_id) {
          toast.warning(t('chat.planReview.cancelled'))
          closeDialog()
        }
      }
    },
  })
})

onUnmounted(() => {
  if (unsubscribe) unsubscribe()
})
</script>

<template>
  <AppSurfaceDialog :open="open" :title="title" @close="closeDialog">
    <div v-if="pending" class="space-y-4">
      <p class="text-sm text-stone-400">
        {{ t('chat.planReview.estimated', { sec: pending.estimatedDurationSec }) }}
      </p>

      <div class="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-amber-100/10 bg-white/[0.03] p-3">
        <div
          v-for="(step, index) in editableSteps"
          :key="step.id"
          class="flex items-start gap-2 rounded-lg border border-amber-100/5 p-2"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 text-sm text-stone-200">
              <span>{{ step.id }}. {{ step.description }}</span>
              <span class="rounded bg-white/10 px-1.5 py-0.5 text-xs text-stone-400">{{ step.tool }}</span>
            </div>
          </div>
          <button
            type="button"
            class="text-xs text-stone-500 hover:text-red-400"
            @click="removeStep(index)"
          >
            {{ t('chat.planReview.removeStep') }}
          </button>
        </div>
      </div>

      <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded-lg border border-amber-100/10 px-4 py-2 text-sm text-stone-300 hover:bg-white/5"
          :disabled="submitting"
          @click="rejectPlan"
        >
          {{ t('chat.planReview.reject') }}
        </button>
        <button
          type="button"
          class="rounded-lg bg-amber-600/90 px-4 py-2 text-sm text-white hover:bg-amber-500"
          :disabled="submitting || editableSteps.length === 0"
          @click="approvePlan"
        >
          {{ t('chat.planReview.approve') }}
        </button>
      </div>
    </div>
  </AppSurfaceDialog>
</template>
