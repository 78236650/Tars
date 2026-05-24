<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import { handoffsApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

export interface PendingHandoff {
  handoffId: string
  sessionId: string
  subagentType: string
  taskSummary: string
  resultPreview: string
}

const chatStore = useChatStore()
const wsStore = useWsStore()
const { t } = useI18n()
const toast = useToast()

const open = ref(false)
const pending = ref<PendingHandoff | null>(null)
const submitting = ref(false)
const error = ref('')

let unsubscribe: (() => void) | null = null

const title = computed(() =>
  pending.value
    ? t('chat.handoff.titleWithType', { type: pending.value.subagentType })
    : t('chat.handoff.title'),
)

const matchesCurrentSession = (sessionId: string) => {
  const current = chatStore.currentSessionId
  return !current || !sessionId || sessionId === current
}

const showHandoff = (data: Record<string, unknown>) => {
  const sessionId = String(data.parent_session_id || data.session_id || '')
  if (!matchesCurrentSession(sessionId)) {
    chatStore.noteExternalHandoff()
    toast.info(t('chat.handoff.otherSessionToast'))
    return
  }
  if (String(data.status || '') !== 'pending_review') return
  pending.value = {
    handoffId: String(data.handoff_id || ''),
    sessionId,
    subagentType: String(data.subagent_type || 'subagent'),
    taskSummary: String(data.task_summary || ''),
    resultPreview: String(data.result_preview || ''),
  }
  error.value = ''
  open.value = true
}

const closeDialog = () => {
  open.value = false
  pending.value = null
  error.value = ''
}

const resolveHandoff = async (action: 'accept' | 'reject') => {
  if (!pending.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    if (action === 'accept') {
      await handoffsApi.accept(pending.value.handoffId)
      toast.success(t('chat.handoff.accepted'))
    } else {
      await handoffsApi.reject(pending.value.handoffId)
      toast.info(t('chat.handoff.rejected'))
    }
    closeDialog()
  } catch {
    error.value = t('chat.handoff.actionFailed')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: Record<string, unknown>) {
      if (data.type === 'subagent_handoff') {
        showHandoff(data)
      }
    },
  })
})

onUnmounted(() => {
  if (unsubscribe) unsubscribe()
})
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    :title="title"
    :description="t('chat.handoff.description')"
    size="md"
    @close="resolveHandoff('reject')"
  >
    <div v-if="pending" class="space-y-4">
      <div class="rounded-xl border border-sky-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-wide text-stone-500">{{ t('chat.handoff.taskLabel') }}</p>
        <p class="mt-1 text-sm text-stone-200">{{ pending.taskSummary }}</p>
      </div>

      <div v-if="pending.resultPreview" class="rounded-xl border border-sky-100/10 bg-[#0c0b09] p-4">
        <p class="mb-2 text-xs uppercase tracking-wide text-stone-500">{{ t('chat.handoff.previewLabel') }}</p>
        <pre class="max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs text-stone-300">{{ pending.resultPreview }}</pre>
      </div>

      <p class="text-sm text-stone-400">{{ t('chat.handoff.hint') }}</p>
      <p v-if="error" class="text-sm text-rose-300">{{ error }}</p>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded-xl border border-rose-400/30 px-4 py-2 text-sm text-rose-200 transition hover:bg-rose-500/10 disabled:opacity-50"
          :disabled="submitting"
          @click="resolveHandoff('reject')"
        >
          {{ t('chat.handoff.reject') }}
        </button>
        <button
          type="button"
          class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="submitting"
          @click="resolveHandoff('accept')"
        >
          {{ submitting ? t('chat.handoff.submitting') : t('chat.handoff.accept') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
