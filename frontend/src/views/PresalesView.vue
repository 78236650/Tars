<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { presalesApi } from '@/api'
import type { PresalesProject } from '@/api'
import BaseCard from '@/components/common/BaseCard.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'

const { t, locale } = useI18n()
const toast = useToast()
const router = useRouter()
const chatStore = useChatStore()

const projects = ref<PresalesProject[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const newProject = ref({ name: '', customer_name: '', industry: '' })
const creating = ref(false)
const switching = ref(false)

const formatTime = (value: string | undefined) => {
  if (!value) return '—'
  return new Date(value).toLocaleString(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

const statusClass = (status: string) => {
  switch (status) {
    case 'completed': return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    case 'archived':  return 'bg-slate-500/15 text-slate-300 border-slate-500/30'
    case 'draft':     return 'bg-stone-500/15 text-stone-300 border-stone-500/30'
    default:          return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
  }
}

const statusLabel = (status: string) => t(`presales.project.status.${status}`) || status

async function loadProjects() {
  loading.value = true
  try {
    const res = await presalesApi.listProjects({ page_size: 50 })
    projects.value = res.projects
  } catch { /* empty */ }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!newProject.value.name.trim()) return
  creating.value = true
  try {
    await presalesApi.createProject({
      name: newProject.value.name.trim(),
      customer_name: newProject.value.customer_name.trim(),
      industry: newProject.value.industry.trim(),
    })
    showCreateDialog.value = false
    newProject.value = { name: '', customer_name: '', industry: '' }
    await loadProjects()
    toast.success(t('common.success'))
  } catch {
    toast.error(t('presales.createFailed'))
  } finally { creating.value = false }
}

async function handleDelete(project: PresalesProject) {
  if (!confirm(t('presales.deleteConfirm'))) return
  try {
    await presalesApi.deleteProject(project.id)
    await loadProjects()
  } catch {
    toast.error(t('common.deleteFailed'))
  }
}

async function openChat(project?: PresalesProject) {
  switching.value = true
  try {
    await chatStore.createSession()
    const prompt = project
      ? `继续「${project.name}」的售前工作。客户: ${project.customer_name || '待定'}，行业: ${project.industry || '待定'}。`
      : '帮我启动售前工作流，我要开始一个新的售前项目'
    await router.replace({ path: '/', query: { prompt } })
  } catch {
    toast.error('切换失败')
  } finally { switching.value = false }
}

onMounted(() => { void loadProjects() })
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Header -->
    <header class="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
      <div>
        <h1 class="text-xl font-semibold text-content">{{ $t('desktop.presales.title') }}</h1>
        <p class="mt-1 text-sm text-content-muted">{{ $t('desktop.presales.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-700 disabled:opacity-50"
          :disabled="switching"
          @click="openChat()"
        >
          <BaseIcon icon="lucide:message-circle" :size="16" class="mr-1.5 inline" />
          开始新售前对话
        </button>
        <button
          type="button"
          class="rounded-lg border border-border px-3 py-2 text-sm text-content-muted hover:bg-surface-2"
          @click="showCreateDialog = true"
        >
          <BaseIcon icon="lucide:plus" :size="16" class="mr-1 inline" />
          {{ t('presales.project.create') }}
        </button>
      </div>
    </header>

    <!-- Project List -->
    <div class="min-h-0 flex-1 overflow-y-auto p-6">
      <div v-if="loading" class="py-12 text-center text-sm text-content-muted">
        {{ t('common.loading') }}
      </div>

      <EmptyState v-else-if="projects.length === 0" :text="t('presales.project.empty')">
        <template #icon>
          <BaseIcon icon="lucide:briefcase" class="h-12 w-12 opacity-40" />
        </template>
      </EmptyState>

      <ul v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="project in projects" :key="project.id">
          <BaseCard class="group cursor-pointer transition hover:border-cyan-500/30" @click="openChat(project)">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <h3 class="truncate font-medium text-content">{{ project.name }}</h3>
                <p v-if="project.customer_name" class="mt-0.5 truncate text-xs text-content-muted">
                  {{ project.customer_name }}
                </p>
              </div>
              <span class="shrink-0 rounded-full border px-2 py-0.5 text-xs" :class="statusClass(project.status)">
                {{ statusLabel(project.status) }}
              </span>
            </div>

            <div class="mt-3 flex items-center gap-3 text-xs text-content-muted">
              <span v-if="project.industry" class="flex items-center gap-1">
                <BaseIcon icon="lucide:building-2" :size="12" /> {{ project.industry }}
              </span>
              <span class="flex items-center gap-1">
                <BaseIcon icon="lucide:clock" :size="12" /> {{ formatTime(project.updated_at) }}
              </span>
            </div>

            <div class="mt-3 flex items-center justify-between">
              <span class="flex items-center gap-1 text-xs text-cyan-400">
                <BaseIcon icon="lucide:message-circle" :size="12" />
                进入对话
              </span>
              <button
                type="button"
                class="rounded px-1.5 py-0.5 text-xs text-content-muted hover:bg-red-500/10 hover:text-red-400"
                @click.stop="handleDelete(project)"
              >
                <BaseIcon icon="lucide:trash-2" :size="14" />
              </button>
            </div>
          </BaseCard>
        </li>
      </ul>
    </div>

    <!-- Create Dialog -->
    <Teleport to="body">
      <div v-if="showCreateDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showCreateDialog = false">
        <div class="w-full max-w-md rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl">
          <h2 class="mb-4 text-lg font-semibold text-content">{{ t('presales.project.create') }}</h2>
          <div class="space-y-3">
            <div>
              <label class="mb-1 block text-xs text-content-muted">{{ t('presales.project.name') }} *</label>
              <input v-model="newProject.name" type="text" class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content placeholder:text-content-muted focus:border-cyan-500/50 focus:outline-none" :placeholder="t('presales.project.name')" @keydown.enter="handleCreate" />
            </div>
            <div>
              <label class="mb-1 block text-xs text-content-muted">{{ t('presales.project.customer') }}</label>
              <input v-model="newProject.customer_name" type="text" class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content placeholder:text-content-muted focus:border-cyan-500/50 focus:outline-none" @keydown.enter="handleCreate" />
            </div>
            <div>
              <label class="mb-1 block text-xs text-content-muted">{{ t('presales.project.industry') }}</label>
              <input v-model="newProject.industry" type="text" class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-content placeholder:text-content-muted focus:border-cyan-500/50 focus:outline-none" @keydown.enter="handleCreate" />
            </div>
          </div>
          <div class="mt-5 flex justify-end gap-2">
            <button type="button" class="rounded-lg border border-border px-4 py-2 text-sm text-content-muted hover:bg-surface-1" @click="showCreateDialog = false">{{ t('common.cancel') }}</button>
            <button type="button" class="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-700 disabled:opacity-50" :disabled="creating || !newProject.name.trim()" @click="handleCreate">{{ creating ? t('common.saving') : t('common.create') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
