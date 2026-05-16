<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import type { Endpoint } from '@/types'

const router = useRouter()
const settingsStore = useSettingsStore()
const toast = useToast()
const { locale, t } = useI18n()

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
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
      <header class="flex shrink-0 items-center justify-between border-b border-amber-100/10 px-6 py-4">
        <div class="flex min-w-0 items-center gap-3">
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 via-orange-500 to-amber-700 shadow-[0_10px_30px_rgba(217,119,6,0.35)]"
          >
            <span class="text-lg font-bold text-stone-950">T</span>
          </div>
          <div class="min-w-0">
            <h1 class="truncate text-lg font-semibold text-stone-100">{{ t('models.title') }}</h1>
            <p class="truncate text-sm text-stone-400">{{ t('models.subtitle') }}</p>
          </div>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div class="mx-auto max-w-5xl space-y-8 p-6 lg:p-8">
          <!-- Ollama -->
          <section class="rounded-[28px] border border-amber-100/10 bg-[#171411]/82 p-6 shadow-[0_24px_80px_rgba(8,7,5,0.28)]">
            <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 class="text-base font-semibold text-stone-100">{{ t('modelsPage.ollamaBlock') }}</h2>
              <div class="flex items-center gap-2 text-sm text-stone-300">
                <span
                  class="h-2 w-2 shrink-0 rounded-full"
                  :class="ollamaConnected ? 'bg-emerald-400' : 'bg-red-500'"
                />
                <code class="break-all rounded-xl border border-amber-100/10 bg-black/25 px-2.5 py-1.5 text-xs text-stone-400">{{
                  settingsStore.ollamaBaseUrl
                }}</code>
              </div>
            </div>
            <p class="mb-4 text-xs text-stone-500">{{ t('modelsPage.ollamaEnvHint') }}</p>
            <div v-if="settingsStore.ollamaModels.length" class="flex flex-wrap gap-2">
              <button
                v-for="m in settingsStore.ollamaModels"
                :key="m"
                type="button"
                @click="selectOllama(m)"
                class="rounded-full border px-3 py-1.5 text-sm transition"
                :class="
                  isCurrentOllama(m)
                    ? 'border-amber-300/60 bg-amber-500 text-stone-950 shadow-[0_12px_30px_rgba(217,119,6,0.25)]'
                    : 'border-amber-100/10 bg-white/[0.04] text-stone-200 hover:border-amber-300/25 hover:bg-amber-500/10'
                "
              >
                {{ m }}
              </button>
            </div>
            <p v-else class="text-sm text-stone-500">{{ t('modelsPage.ollamaEmpty') }}</p>
          </section>

          <!-- OpenAI-compatible -->
          <section class="rounded-[28px] border border-amber-100/10 bg-[#171411]/82 p-6 shadow-[0_24px_80px_rgba(8,7,5,0.28)]">
            <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
              <h2 class="text-base font-semibold text-stone-100">{{ t('modelsPage.remoteBlock') }}</h2>
              <button
                type="button"
                @click="showAddEndpoint = !showAddEndpoint"
                class="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-400"
              >
                + {{ t('modelsPage.addEndpoint') }}
              </button>
            </div>

            <div
              v-if="showAddEndpoint"
              class="mb-6 space-y-3 rounded-[24px] border border-amber-100/10 bg-black/20 p-4"
            >
              <input
                v-model="addForm.name"
                type="text"
                :placeholder="t('modelsPage.namePh')"
                class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
              />
              <input
                v-model="addForm.base_url"
                type="url"
                :placeholder="t('modelsPage.baseUrlPh')"
                class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
              />
              <input
                v-model="addForm.api_key"
                type="password"
                autocomplete="off"
                :placeholder="t('modelsPage.apiKeyPh')"
                class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
              />
              <div class="flex justify-end gap-2">
                <button
                  type="button"
                  @click="showAddEndpoint = false"
                  class="px-3 py-2 text-sm text-stone-400 transition hover:text-stone-100"
                >
                  {{ t('common.cancel') }}
                </button>
                <button
                  type="button"
                  @click="createEndpoint"
                  class="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-400"
                >
                  {{ t('common.create') }}
                </button>
              </div>
            </div>

            <div v-if="!settingsStore.endpoints.length" class="py-8 text-center text-sm text-stone-500">
              {{ t('modelsPage.noEndpoints') }}
            </div>

            <div v-else class="space-y-4">
              <div
                v-for="ep in settingsStore.endpoints"
                :key="ep.id"
                class="rounded-[24px] border border-amber-100/10 bg-white/[0.03] p-4"
              >
                <div class="mb-3 flex flex-wrap items-start justify-between gap-2">
                  <div class="min-w-0">
                    <h3 class="truncate font-medium text-stone-100">{{ ep.name }}</h3>
                    <p class="mt-0.5 truncate text-xs text-stone-500" :title="ep.base_url">{{ ep.base_url }}</p>
                  </div>
                  <div class="flex shrink-0 flex-wrap gap-2">
                    <button
                      type="button"
                      :disabled="busyEndpointId === ep.id"
                      @click="fetchModels(ep.id)"
                      class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10 disabled:opacity-50"
                    >
                      {{ t('modelsPage.fetchModels') }}
                    </button>
                    <button
                      type="button"
                      :disabled="busyEndpointId === ep.id"
                      @click="testConn(ep.id)"
                      class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10 disabled:opacity-50"
                    >
                      {{ t('common.test') }}
                    </button>
                    <button
                      type="button"
                      @click="openEdit(ep)"
                      class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
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
                    class="rounded-full border px-3 py-1.5 text-sm transition disabled:opacity-40"
                    :class="
                      isCurrentRemote(ep, mod)
                        ? 'border-amber-300/60 bg-amber-500 text-stone-950 shadow-[0_12px_30px_rgba(217,119,6,0.25)]'
                        : 'border-amber-100/10 bg-white/[0.04] text-stone-200 hover:border-amber-300/25 hover:bg-amber-500/10'
                    "
                  >
                    {{ mod }}
                  </button>
                </div>
                <div v-else class="space-y-2">
                  <p class="text-xs text-stone-500">{{ t('modelsPage.noModelsHint') }}</p>
                  <button
                    type="button"
                    @click="openManual(ep)"
                    class="text-xs text-amber-300 transition hover:text-amber-200"
                  >
                    {{ t('modelsPage.manualModels') }}
                  </button>
                  <div v-if="manualTargetId === ep.id" class="flex flex-col gap-2 mt-2">
                    <textarea
                      v-model="manualModelsText"
                      rows="3"
                      :placeholder="t('modelsPage.manualPlaceholder')"
                      class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 font-mono text-xs text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
                    />
                    <button
                      type="button"
                      @click="applyManualModels(ep)"
                      class="self-end rounded-xl bg-amber-500 px-3 py-1.5 text-xs font-medium text-stone-950 transition hover:bg-amber-400"
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

    <!-- Edit modal -->
    <div
      v-if="editingEndpoint"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      @click.self="closeEdit"
    >
      <div class="w-full max-w-md rounded-[28px] border border-amber-100/10 bg-[#171411] p-5 shadow-[0_30px_100px_rgba(8,7,5,0.65)]">
        <h3 class="mb-4 text-lg font-semibold text-stone-100">{{ t('modelsPage.editEndpoint') }}</h3>
        <div class="space-y-3">
          <input
            v-model="editForm.name"
            type="text"
            class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 focus:border-amber-300/30 focus:outline-none"
          />
          <input
            v-model="editForm.base_url"
            type="url"
            class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 focus:border-amber-300/30 focus:outline-none"
          />
          <input
            v-model="editForm.api_key"
            type="password"
            autocomplete="off"
            :placeholder="t('modelsPage.apiKeyLeaveBlank')"
            class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
          />
          <label class="block text-xs text-stone-400">{{ t('modelsPage.modelsOnePerLine') }}</label>
          <textarea
            v-model="editForm.modelsText"
            rows="5"
            class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 font-mono text-xs text-stone-100 focus:border-amber-300/30 focus:outline-none"
          />
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <button type="button" @click="closeEdit" class="px-3 py-2 text-sm text-stone-400 transition hover:text-stone-100">
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            @click="saveEdit"
            class="rounded-2xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-amber-400"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
