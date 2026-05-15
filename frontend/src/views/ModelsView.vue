<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import Sidebar from '@/components/layout/Sidebar.vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import type { Endpoint } from '@/types'

const router = useRouter()
const settingsStore = useSettingsStore()
const toast = useToast()
const { locale, toggleLocale, t } = useI18n()

const showAddEndpoint = ref(false)
const editingEndpoint = ref<Endpoint | null>(null)
const manualModelsText = ref('')
const addForm = ref({ name: '', base_url: '', api_key: '' })
const editForm = ref({ name: '', base_url: '', api_key: '', modelsText: '' })
const busyEndpointId = ref<string | null>(null)

function formatApiError(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as unknown
    if (typeof d === 'string') return d
    if (d && typeof d === 'object' && 'detail' in d) {
      const det = (d as { detail: unknown }).detail
      if (typeof det === 'string') return det
      if (Array.isArray(det)) {
        return det
          .map((x: { msg?: string; loc?: unknown }) => x?.msg || JSON.stringify(x))
          .filter(Boolean)
          .join('; ')
      }
    }
    return e.message || 'Request failed'
  }
  if (e instanceof Error) return e.message
  return String(e)
}

onMounted(() => {
  settingsStore.loadModels()
})

const ollamaConnected = computed(() => settingsStore.ollamaStatus === 'connected')

const selectOllama = async (name: string) => {
  const ok = await settingsStore.applyModelSelection('ollama', name)
  if (ok) toast.success(t('modelsPage.switched'))
  else toast.error(t('sidebar.switchFailed'))
}

const selectRemote = async (ep: Endpoint, model: string) => {
  if (!ep.enabled) return
  const ok = await settingsStore.applyModelSelection('openai_compatible', model, ep.id)
  if (ok) toast.success(t('modelsPage.switched'))
  else toast.error(t('sidebar.switchFailed'))
}

const isCurrentOllama = (name: string) =>
  settingsStore.currentProvider === 'ollama' && settingsStore.currentModel === name

const isCurrentRemote = (ep: Endpoint, model: string) =>
  settingsStore.currentProvider === 'openai_compatible' &&
  settingsStore.currentEndpointId === ep.id &&
  settingsStore.currentModel === model

const openEdit = (ep: Endpoint) => {
  editingEndpoint.value = ep
  editForm.value = {
    name: ep.name,
    base_url: ep.base_url,
    api_key: ep.api_key || '',
    modelsText: (ep.models || []).join('\n'),
  }
}

const closeEdit = () => {
  editingEndpoint.value = null
}

const saveEdit = async () => {
  if (!editingEndpoint.value) return
  const models = editForm.value.modelsText
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  const payload: Record<string, unknown> = {
    name: editForm.value.name,
    base_url: editForm.value.base_url,
    models,
  }
  if (editForm.value.api_key.trim()) {
    payload.api_key = editForm.value.api_key.trim()
  }
  try {
    await settingsStore.updateEndpoint(editingEndpoint.value.id, payload as any)
    toast.success(t('common.success'))
    closeEdit()
  } catch (e) {
    toast.error(formatApiError(e))
  }
}

const createEndpoint = async () => {
  if (!addForm.value.name.trim() || !addForm.value.base_url.trim()) {
    toast.error(t('modelsPage.fillRequired'))
    return
  }
  try {
    await settingsStore.createEndpoint({
      name: addForm.value.name.trim(),
      base_url: addForm.value.base_url.trim(),
      api_key: addForm.value.api_key.trim() || undefined,
    })
    toast.success(t('modelsPage.endpointCreated'))
    showAddEndpoint.value = false
    addForm.value = { name: '', base_url: '', api_key: '' }
  } catch (e) {
    toast.error(formatApiError(e))
  }
}

const removeEndpoint = async (id: string) => {
  if (!confirm(t('modelsPage.deleteConfirm'))) return
  try {
    await settingsStore.deleteEndpoint(id)
    toast.success(t('common.success'))
  } catch (e) {
    toast.error(formatApiError(e))
  }
}

const fetchModels = async (id: string) => {
  busyEndpointId.value = id
  try {
    const r = await settingsStore.fetchEndpointModels(id)
    if (r.success) {
      if (r.models?.length) {
        toast.success(`${t('modelsPage.fetchOkPrefix')} ${r.models.length}`)
      } else {
        toast.success(t('modelsPage.fetchEmpty'))
      }
      void settingsStore.loadModels().catch(() => {})
    }
  } catch (e) {
    toast.error(formatApiError(e))
  } finally {
    busyEndpointId.value = null
  }
}

const testConn = async (id: string) => {
  busyEndpointId.value = id
  try {
    const r = await settingsStore.testEndpoint(id)
    toast[r.success ? 'success' : 'error'](r.message)
  } catch (e) {
    toast.error(formatApiError(e))
  } finally {
    busyEndpointId.value = null
  }
}

const applyManualModels = async (ep: Endpoint) => {
  const models = manualModelsText.value
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (!models.length) {
    toast.error(t('modelsPage.manualEmpty'))
    return
  }
  try {
    await settingsStore.updateEndpoint(ep.id, { models })
    toast.success(t('common.success'))
    manualModelsText.value = ''
    void settingsStore.loadModels().catch(() => {})
  } catch (e) {
    toast.error(formatApiError(e))
  }
}

const manualTargetId = ref<string | null>(null)
const openManual = (ep: Endpoint) => {
  manualTargetId.value = manualTargetId.value === ep.id ? null : ep.id
  manualModelsText.value = ''
}
</script>

<template>
  <div class="flex h-screen bg-slate-900">
    <Sidebar />

    <main class="flex-1 flex flex-col min-w-0">
      <header class="flex items-center justify-between px-6 py-4 border-b border-slate-700 shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <div
            class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center shrink-0"
          >
            <span class="text-white font-bold text-lg">T</span>
          </div>
          <div class="min-w-0">
            <h1 class="text-lg font-semibold text-white truncate">{{ t('models.title') }}</h1>
            <p class="text-sm text-slate-400 truncate">{{ t('models.subtitle') }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3 shrink-0">
          <button
            type="button"
            @click="toggleLocale"
            class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
          >
            {{ locale === 'zh' ? 'EN' : '中文' }}
          </button>
          <button
            type="button"
            @click="router.push('/')"
            class="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors text-sm"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 19l-7-7 7-7"
              />
            </svg>
            <span>{{ t('models.backToChat') }}</span>
          </button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div class="max-w-4xl mx-auto p-8 space-y-10">
          <!-- Ollama -->
          <section class="rounded-xl border border-slate-700 bg-slate-800/40 p-6">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h2 class="text-base font-semibold text-white">{{ t('modelsPage.ollamaBlock') }}</h2>
              <div class="flex items-center gap-2 text-sm text-slate-300">
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  :class="ollamaConnected ? 'bg-emerald-400' : 'bg-red-500'"
                />
                <code class="text-xs bg-slate-900/80 px-2 py-1 rounded text-slate-400 break-all">{{
                  settingsStore.ollamaBaseUrl
                }}</code>
              </div>
            </div>
            <p class="text-xs text-slate-500 mb-4">{{ t('modelsPage.ollamaEnvHint') }}</p>
            <div v-if="settingsStore.ollamaModels.length" class="flex flex-wrap gap-2">
              <button
                v-for="m in settingsStore.ollamaModels"
                :key="m"
                type="button"
                @click="selectOllama(m)"
                class="px-3 py-1.5 rounded-full text-sm border transition-colors"
                :class="
                  isCurrentOllama(m)
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-slate-700/80 border-slate-600 text-slate-200 hover:border-slate-500'
                "
              >
                {{ m }}
              </button>
            </div>
            <p v-else class="text-sm text-slate-500">{{ t('modelsPage.ollamaEmpty') }}</p>
          </section>

          <!-- OpenAI-compatible -->
          <section class="rounded-xl border border-slate-700 bg-slate-800/40 p-6">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
              <h2 class="text-base font-semibold text-white">{{ t('modelsPage.remoteBlock') }}</h2>
              <button
                type="button"
                @click="showAddEndpoint = !showAddEndpoint"
                class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm transition-colors"
              >
                + {{ t('modelsPage.addEndpoint') }}
              </button>
            </div>

            <div
              v-if="showAddEndpoint"
              class="mb-6 p-4 rounded-lg border border-slate-600 bg-slate-900/50 space-y-3"
            >
              <input
                v-model="addForm.name"
                type="text"
                :placeholder="t('modelsPage.namePh')"
                class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm"
              />
              <input
                v-model="addForm.base_url"
                type="url"
                :placeholder="t('modelsPage.baseUrlPh')"
                class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm"
              />
              <input
                v-model="addForm.api_key"
                type="password"
                autocomplete="off"
                :placeholder="t('modelsPage.apiKeyPh')"
                class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm"
              />
              <div class="flex gap-2 justify-end">
                <button
                  type="button"
                  @click="showAddEndpoint = false"
                  class="px-3 py-2 text-sm text-slate-400 hover:text-white"
                >
                  {{ t('common.cancel') }}
                </button>
                <button
                  type="button"
                  @click="createEndpoint"
                  class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm"
                >
                  {{ t('common.create') }}
                </button>
              </div>
            </div>

            <div v-if="!settingsStore.endpoints.length" class="text-center py-8 text-slate-500 text-sm">
              {{ t('modelsPage.noEndpoints') }}
            </div>

            <div v-else class="space-y-4">
              <div
                v-for="ep in settingsStore.endpoints"
                :key="ep.id"
                class="rounded-lg border border-slate-600 bg-slate-900/30 p-4"
              >
                <div class="flex flex-wrap items-start justify-between gap-2 mb-3">
                  <div class="min-w-0">
                    <h3 class="text-white font-medium truncate">{{ ep.name }}</h3>
                    <p class="text-xs text-slate-500 truncate mt-0.5" :title="ep.base_url">{{ ep.base_url }}</p>
                  </div>
                  <div class="flex flex-wrap gap-2 shrink-0">
                    <button
                      type="button"
                      :disabled="busyEndpointId === ep.id"
                      @click="fetchModels(ep.id)"
                      class="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-50"
                    >
                      {{ t('modelsPage.fetchModels') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyEndpointId === ep.id"
                      @click="testConn(ep.id)"
                      class="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-200 disabled:opacity-50"
                    >
                      {{ t('common.test') }}
                    </button>
                    <button
                      type="button"
                      @click="openEdit(ep)"
                      class="px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-200"
                    >
                      {{ t('common.edit') }}
                    </button>
                    <button
                      type="button"
                      @click="removeEndpoint(ep.id)"
                      class="px-2 py-1 text-xs rounded bg-red-900/40 hover:bg-red-800/60 text-red-200"
                    >
                      {{ t('common.delete') }}
                    </button>
                  </div>
                </div>

                <div v-if="ep.models?.length" class="flex flex-wrap gap-2">
                  <button
                    v-for="mod in ep.models"
                    :key="mod"
                    type="button"
                    :disabled="!ep.enabled"
                    @click="selectRemote(ep, mod)"
                    class="px-3 py-1.5 rounded-full text-sm border transition-colors disabled:opacity-40"
                    :class="
                      isCurrentRemote(ep, mod)
                        ? 'bg-emerald-700 border-emerald-500 text-white'
                        : 'bg-slate-700/80 border-slate-600 text-slate-200 hover:border-slate-500'
                    "
                  >
                    {{ mod }}
                  </button>
                </div>
                <div v-else class="space-y-2">
                  <p class="text-xs text-slate-500">{{ t('modelsPage.noModelsHint') }}</p>
                  <button
                    type="button"
                    @click="openManual(ep)"
                    class="text-xs text-blue-400 hover:underline"
                  >
                    {{ t('modelsPage.manualModels') }}
                  </button>
                  <div v-if="manualTargetId === ep.id" class="flex flex-col gap-2 mt-2">
                    <textarea
                      v-model="manualModelsText"
                      rows="3"
                      :placeholder="t('modelsPage.manualPlaceholder')"
                      class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-xs font-mono"
                    />
                    <button
                      type="button"
                      @click="applyManualModels(ep)"
                      class="self-end px-3 py-1.5 text-xs rounded bg-blue-600 text-white"
                    >
                      {{ t('common.save') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>

    <!-- Edit modal -->
    <div
      v-if="editingEndpoint"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      @click.self="closeEdit"
    >
      <div class="w-full max-w-md rounded-xl border border-slate-600 bg-slate-800 p-5 shadow-2xl">
        <h3 class="text-lg font-semibold text-white mb-4">{{ t('modelsPage.editEndpoint') }}</h3>
        <div class="space-y-3">
          <input
            v-model="editForm.name"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white text-sm"
          />
          <input
            v-model="editForm.base_url"
            type="url"
            class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white text-sm"
          />
          <input
            v-model="editForm.api_key"
            type="password"
            autocomplete="off"
            :placeholder="t('modelsPage.apiKeyLeaveBlank')"
            class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white text-sm"
          />
          <label class="block text-xs text-slate-400">{{ t('modelsPage.modelsOnePerLine') }}</label>
          <textarea
            v-model="editForm.modelsText"
            rows="5"
            class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white text-xs font-mono"
          />
        </div>
        <div class="flex justify-end gap-2 mt-5">
          <button type="button" @click="closeEdit" class="px-3 py-2 text-sm text-slate-400 hover:text-white">
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            @click="saveEdit"
            class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
