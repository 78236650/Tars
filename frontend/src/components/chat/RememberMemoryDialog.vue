<script setup lang="ts">
import { ref, watch } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import { memoryApi } from '@/api'
import { useI18n } from '@/i18n'

export interface MemoryDraftItem {
  content: string
  category: string
  importance: number
  selected: boolean
}

const props = defineProps<{
  open: boolean
  userContent: string
  assistantContent: string
}>()

const emit = defineEmits<{
  close: []
  saved: [memoryCount: number, knowledgeCount: number, promotionTrigger?: string]
}>()

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const drafts = ref<MemoryDraftItem[]>([])
const publishToKnowledge = ref(false)

const categoryOptions = [
  { value: 'fact', labelKey: 'chat.remember.category.fact' },
  { value: 'preference', labelKey: 'chat.remember.category.preference' },
  { value: 'decision', labelKey: 'chat.remember.category.decision' },
  { value: 'domain_knowledge', labelKey: 'chat.remember.category.domainKnowledge' },
]

const loadDrafts = async () => {
  loading.value = true
  error.value = ''
  drafts.value = []
  try {
    const data = await memoryApi.extractFromTurn({
      user_content: props.userContent,
      assistant_content: props.assistantContent,
    })
    drafts.value = (data.items || []).map((item) => ({
      content: item.content,
      category: item.category || 'fact',
      importance: item.importance ?? 0.75,
      selected: true,
    }))
    if (drafts.value.length === 0) {
      error.value = t('chat.remember.empty')
      addDraft()
    }
  } catch {
    error.value = t('chat.remember.extractFailed')
  } finally {
    loading.value = false
  }
}

const addDraft = () => {
  drafts.value.push({
    content: '',
    category: 'fact',
    importance: 0.75,
    selected: true,
  })
}

const saveDrafts = async () => {
  const items = drafts.value
    .filter((item) => item.selected && item.content.trim().length >= 5)
    .map(({ content, category, importance }) => ({
      content: content.trim(),
      category,
      importance,
    }))

  if (items.length === 0) {
    error.value = t('chat.remember.nothingSelected')
    return
  }

  saving.value = true
  error.value = ''
  try {
    const result = await memoryApi.saveFromTurn({
      items,
      user_context: props.userContent,
      publish_to_knowledge: publishToKnowledge.value,
    })
    const kbCount = result.knowledge_doc_ids?.length || 0
    emit('saved', result.saved.length, kbCount, result.promotion_trigger)
    emit('close')
  } catch {
    error.value = t('chat.remember.saveFailed')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) loadDrafts()
  },
)
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    :title="t('chat.remember.title')"
    :description="t('chat.remember.description')"
    size="md"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <p v-if="loading" class="text-sm text-stone-400">{{ t('chat.remember.loading') }}</p>

      <template v-else>
        <p v-if="error && drafts.length === 0" class="text-sm text-amber-300/90">{{ error }}</p>

        <div v-if="drafts.length" class="space-y-3">
          <div
            v-for="(draft, index) in drafts"
            :key="index"
            class="rounded-xl border border-amber-100/10 bg-white/[0.03] p-3"
          >
            <label class="mb-2 flex items-center gap-2 text-xs text-stone-400">
              <input v-model="draft.selected" type="checkbox" class="rounded border-stone-600" />
              {{ t('chat.remember.selectItem') }}
            </label>
            <textarea
              v-model="draft.content"
              rows="2"
              class="mb-2 w-full resize-y rounded-lg border border-amber-100/10 bg-surface-0 px-3 py-2 text-sm text-stone-100 outline-none focus:border-amber-300/25"
            />
            <select
              v-model="draft.category"
              class="w-full rounded-lg border border-amber-100/10 bg-surface-0 px-3 py-2 text-sm text-stone-200 outline-none focus:border-amber-300/25"
            >
              <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
                {{ t(opt.labelKey) }}
              </option>
            </select>
          </div>
        </div>

        <button
          type="button"
          class="text-xs text-amber-400 transition hover:text-amber-300"
          @click="addDraft"
        >
          + {{ t('chat.remember.addManual') }}
        </button>

        <label class="flex items-start gap-2 rounded-lg border border-amber-100/10 bg-white/[0.02] p-3 text-sm text-stone-300">
          <input v-model="publishToKnowledge" type="checkbox" class="mt-0.5 rounded border-stone-600" />
          <span>
            <span class="block text-stone-200">{{ t('chat.remember.publishNow') }}</span>
            <span class="mt-1 block text-xs text-stone-500">{{ t('chat.remember.publishHint') }}</span>
          </span>
        </label>

        <p v-if="error && drafts.length > 0" class="text-sm text-rose-300">{{ error }}</p>
      </template>

      <div class="flex justify-end gap-2 border-t border-amber-100/10 pt-4">
        <button
          type="button"
          class="rounded-xl px-4 py-2 text-sm text-stone-300 transition hover:bg-white/[0.04]"
          @click="emit('close')"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="loading || saving"
          @click="saveDrafts"
        >
          {{ saving ? t('chat.remember.saving') : t('chat.remember.save') }}
        </button>
      </div>
    </div>
  </AppSurfaceDialog>
</template>
