<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeApi } from '@/api'
import { useI18n } from '@/i18n'

const props = defineProps<{
  open: boolean
  docId: string
  titleHint?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const title = ref('')
const snippet = ref('')
const error = ref('')

const loadRef = async (docId: string) => {
  if (!docId) return
  loading.value = true
  error.value = ''
  title.value = props.titleHint || docId
  snippet.value = ''
  try {
    const resp = await knowledgeApi.resolveRef(docId)
    title.value = resp.data.title || docId
    snippet.value = resp.data.snippet || ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail || t('chat.citationLoadFailed')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.docId] as const,
  ([open, docId]) => {
    if (open && docId) loadRef(docId)
  },
  { immediate: true },
)

const openInKnowledge = () => {
  router.push({ path: '/knowledge', query: { doc_id: props.docId } })
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex justify-end bg-black/40"
      @click.self="emit('close')"
    >
      <aside class="flex h-full w-full max-w-md flex-col border-l border-amber-100/10 bg-surface-1 shadow-2xl">
        <div class="flex items-start justify-between gap-3 border-b border-amber-100/10 px-5 py-4">
          <div class="min-w-0">
            <p class="text-xs uppercase tracking-[0.18em] text-stone-500">{{ t('chat.citationPreview') }}</p>
            <h3 class="mt-2 truncate text-lg font-semibold text-stone-100">{{ title }}</h3>
            <p class="mt-1 truncate text-xs text-stone-500">{{ docId }}</p>
          </div>
          <button
            type="button"
            class="rounded-xl p-2 text-stone-400 transition hover:bg-white/[0.06] hover:text-stone-200"
            @click="emit('close')"
          >
            ✕
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-5 py-4">
          <div v-if="loading" class="text-sm text-stone-400">{{ t('common.loading') }}</div>
          <div v-else-if="error" class="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
            {{ error }}
          </div>
          <div v-else-if="snippet" class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4 text-sm leading-relaxed text-stone-300 whitespace-pre-wrap">
            {{ snippet }}
          </div>
          <div v-else class="text-sm text-stone-500">{{ t('chat.citationEmpty') }}</div>
        </div>

        <div class="border-t border-amber-100/10 px-5 py-4">
          <button
            type="button"
            class="w-full rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-medium text-stone-950 transition hover:bg-amber-400"
            @click="openInKnowledge"
          >
            {{ t('chat.openInKnowledge') }}
          </button>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
