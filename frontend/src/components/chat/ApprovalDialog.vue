<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import { approvalsApi } from '@/api'
import { useChatStore } from '@/stores/chat'
import { useWsStore } from '@/stores/wsStore'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

export interface PendingApproval {
  approvalId: string
  sessionId: string
  toolName: string
  argumentsSummary: string
}

const chatStore = useChatStore()
const wsStore = useWsStore()
const { t } = useI18n()
const toast = useToast()

const open = ref(false)
const pending = ref<PendingApproval | null>(null)
const submitting = ref(false)
const error = ref('')

let unsubscribe: (() => void) | null = null

const title = computed(() =>
  pending.value
    ? t('chat.approval.titleWithTool', { tool: pending.value.toolName })
    : t('chat.approval.title'),
)

const matchesCurrentSession = (sessionId: string) => {
  const current = chatStore.currentSessionId
  return !current || !sessionId || sessionId === current
}

const showApproval = (data: Record<string, unknown>) => {
  const sessionId = String(data.session_id || '')
  if (!matchesCurrentSession(sessionId)) {
    chatStore.noteExternalApproval()
    toast.info(t('chat.approval.otherSessionToast'))
    return
  }
  pending.value = {
    approvalId: String(data.approval_id || ''),
    sessionId,
    toolName: String(data.tool_name || 'tool'),
    argumentsSummary: String(data.arguments_summary || ''),
  }
  error.value = ''
  open.value = true
}

const closeDialog = () => {
  open.value = false
  pending.value = null
  error.value = ''
}

const resolveApproval = async (action: 'approve' | 'deny') => {
  if (!pending.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    if (action === 'approve') {
      await approvalsApi.approve(pending.value.approvalId)
      toast.success(t('chat.approval.approved'))
    } else {
      await approvalsApi.deny(pending.value.approvalId)
      toast.info(t('chat.approval.denied'))
    }
    closeDialog()
  } catch {
    error.value = t('chat.approval.actionFailed')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  unsubscribe = wsStore.subscribe({
    onMessage(data: Record<string, unknown>) {
      if (data.type === 'approval_required') {
        showApproval(data)
        return
      }
      if (data.type === 'approval_resolved') {
        const approvalId = String(data.approval_id || '')
        if (pending.value?.approvalId === approvalId) {
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
  <AppSurfaceDialog
    :open="open"
    :title="title"
    :description="t('chat.approval.description')"
    size="md"
    @close="resolveApproval('deny')"
  >
    <div v-if="pending" class="space-y-4">
      <div class="rounded-xl border border-amber-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-wide text-stone-500">{{ t('chat.approval.toolLabel') }}</p>
        <p class="mt-1 font-mono text-sm text-amber-200">{{ pending.toolName }}</p>
      </div>

      <div v-if="pending.argumentsSummary" class="rounded-xl border border-amber-100/10 bg-[#0c0b09] p-4">
        <p class="mb-2 text-xs uppercase tracking-wide text-stone-500">{{ t('chat.approval.argsLabel') }}</p>
        <pre class="max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs text-stone-300">{{ pending.argumentsSummary }}</pre>
      </div>

      <p class="text-sm text-stone-400">{{ t('chat.approval.hint') }}</p>
      <p v-if="error" class="text-sm text-rose-300">{{ error }}</p>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded-xl border border-rose-400/30 px-4 py-2 text-sm text-rose-200 transition hover:bg-rose-500/10 disabled:opacity-50"
          :disabled="submitting"
          @click="resolveApproval('deny')"
        >
          {{ t('chat.approval.deny') }}
        </button>
        <button
          type="button"
          class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="submitting"
          @click="resolveApproval('approve')"
        >
          {{ submitting ? t('chat.approval.submitting') : t('chat.approval.approve') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
