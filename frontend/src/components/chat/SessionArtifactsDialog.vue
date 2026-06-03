<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { sessionsApi } from '@/api'
import type { SessionArtifactItem, SessionArtifactsData } from '@/types'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  open: boolean
  sessionId: string | null
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const toast = useToast()

const loading = ref(false)
const data = ref<SessionArtifactsData | null>(null)

const groupedItems = computed(() => {
  const items = data.value?.items || []
  const groups = new Map<string, SessionArtifactItem[]>()
  for (const item of items) {
    const key = item.directory || '/'
    const bucket = groups.get(key) || []
    bucket.push(item)
    groups.set(key, bucket)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
})

const sourceLabel = (source: string) => {
  if (source === 'task') return t('chat.artifacts.sourceTask')
  if (source === 'workspace') return t('chat.artifacts.sourceWorkspace')
  return source
}

async function loadArtifacts() {
  if (!props.sessionId) {
    data.value = null
    return
  }
  loading.value = true
  try {
    data.value = await sessionsApi.getArtifacts(props.sessionId)
  } catch (e) {
    console.error(e)
    toast.error(t('chat.artifacts.loadFailed'))
    data.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.sessionId] as const,
  ([open]) => {
    if (open) void loadArtifacts()
  },
)
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    :title="t('chat.artifacts.title')"
    :description="t('chat.artifacts.subtitle')"
    size="lg"
    @close="emit('close')"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 pb-6">
      <div v-if="loading" class="py-8 text-center text-sm text-stone-400">
        {{ t('common.loading') }}
      </div>

      <template v-else-if="data">
        <section class="rounded-xl border border-amber-100/10 bg-white/[0.03] p-4">
          <p class="text-xs font-medium uppercase tracking-wide text-stone-500">
            {{ t('chat.artifacts.workspace') }}
          </p>
          <p class="mt-2 break-all font-mono text-sm text-stone-200">{{ data.workspace_path }}</p>
          <p v-if="data.workspace_source" class="mt-1 text-xs text-stone-500">
            {{ t('chat.artifacts.workspaceSource', { source: data.workspace_source }) }}
          </p>
        </section>

        <section v-if="data.tasks.length" class="space-y-2">
          <h3 class="text-sm font-semibold text-stone-200">{{ t('chat.artifacts.tasks') }}</h3>
          <div
            v-for="task in data.tasks"
            :key="task.id"
            class="rounded-xl border border-amber-100/10 bg-white/[0.02] p-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-stone-200">{{ task.title }}</p>
                <p class="mt-0.5 truncate text-xs text-stone-500">{{ task.goal }}</p>
              </div>
              <span class="shrink-0 rounded-full border border-amber-100/15 px-2 py-0.5 text-[10px] text-stone-400">
                {{ task.status }}
              </span>
            </div>
            <p v-if="task.workspace_path" class="mt-2 break-all font-mono text-[11px] text-stone-500">
              {{ task.workspace_path }}
            </p>
            <p v-if="task.output_summary" class="mt-2 text-xs text-stone-400">{{ task.output_summary }}</p>
          </div>
        </section>

        <section>
          <div class="mb-3 flex items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-stone-200">
              {{ t('chat.artifacts.files') }}
              <span class="ml-1 text-xs font-normal text-stone-500">({{ data.total }})</span>
            </h3>
          </div>

          <EmptyState v-if="!data.items.length" :text="t('chat.artifacts.empty')" class="py-8" />

          <div v-else class="space-y-4">
            <div v-for="[directory, files] in groupedItems" :key="directory">
              <p class="mb-2 flex items-center gap-1.5 text-xs font-medium text-stone-500">
                <BaseIcon icon="lucide:folder" :size="14" />
                <span>{{ directory === '/' ? t('chat.artifacts.rootDir') : directory }}</span>
              </p>
              <ul class="space-y-1.5">
                <li
                  v-for="file in files"
                  :key="`${file.source}-${file.path}`"
                  class="flex items-start gap-2 rounded-lg border border-amber-100/10 bg-stone-950/40 px-3 py-2"
                >
                  <BaseIcon icon="lucide:file" :size="14" class="mt-0.5 shrink-0 text-amber-400" />
                  <div class="min-w-0 flex-1">
                    <p class="truncate font-mono text-sm text-stone-200">{{ file.path }}</p>
                    <p class="mt-0.5 text-[11px] text-stone-500">
                      {{ sourceLabel(file.source) }}
                      <template v-if="file.task_title"> · {{ file.task_title }}</template>
                    </p>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </section>
      </template>
    </div>
  </AppSurfaceDialog>
</template>
