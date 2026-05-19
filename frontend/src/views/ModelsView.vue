<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import { providersApi, type ProviderInfo } from '@/api'
import type { Endpoint } from '@/types'

const router = useRouter()
const settingsStore = useSettingsStore()
const toast = useToast()
const { t } = useI18n()

const showAddEndpoint = ref(false)
const editingEndpoint = ref<Endpoint | null>(null)
const manualModelsText = ref('')
const addForm = ref({ name: '', base_url: '', api_key: '' })
const editForm = ref({ name: '', base_url: '', api_key: '', modelsText: '' })
const busyEndpointId = ref<string | null>(null)

// v4.0.0: Provider 列表
const providers = ref<ProviderInfo[]>([])
const providerStatuses = ref<Record<string, string>>({})

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

onMounted(async () => {
  settingsStore.loadModels()
  try {
    const provs = await providersApi.list()
    providers.value = provs
  } catch {
    console.error('Failed to load providers')
  }
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

// v4.0.0: Provider 测试连接
const testProvider = async (name: string) => {
  if (providerStatuses.value[name] === 'testing') return
  providerStatuses.value[name] = 'testing'
  try {
    const res = await providersApi.test(name)
    providerStatuses.value[name] = res.status === 'ok' ? 'ok' : 'error'
  } catch {
    providerStatuses.value[name] = 'error'
  }
}

const getProviderStatus = (name: string): string => {
  if (providerStatuses.value[name]) return providerStatuses.value[name]
  // 对于 ollama，使用 settingsStore 的状态
  if (name === 'ollama') return ollamaConnected.value ? 'ok' : 'disconnected'
  return 'unknown'
}

const providerStatusLabel = (name: string): string => {
  const status = getProviderStatus(name)
  if (status === 'ok') return t('modelsPage.online')
  if (status === 'disconnected') return t('modelsPage.disconnected')
  return t('modelsPage.offline')
}

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

const openManual = (ep: Endpoint) => {
  manualTargetId.value = manualTargetId.value === ep.id ? null : ep.id
  manualModelsText.value = (ep.models || []).join('\n')
}

const applyManualModels = async (ep: Endpoint) => {
  const models = manualModelsText.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  try {
    await settingsStore.updateEndpoint(ep.id, { models })
    toast.success(t('common.success'))
    manualTargetId.value = null
  } catch (e) {
    toast.error(formatApiError(e))
  }
}

const manualTargetId = ref<string | null>(null)

const fetchModels = async (id: string) => {
  busyEndpointId.value = id
  try {
    const res = await settingsStore.fetchEndpointModels(id)
    const count = (res.models || []).length
    toast.success(count > 0 ? t('modelsPage.fetchOk', { count }) : t('modelsPage.fetchEmpty'))
  } catch (e) {
    toast.error(formatApiError(e))
  } finally {
    busyEndpointId.value = null
  }
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
    <main class="flex-1 min-h-0 overflow-hidden">
      <div class="h-full overflow-y-auto px-6 py-6 space-y-6">

        <!-- v4.0.0: Provider 分组卡片 -->
        <section v-if="providers.length > 0" class="space-y-4">
          <h2 class="text-sm font-medium text-stone-400 uppercase tracking-[0.08em]">{{ t('modelsPage.providers') }}</h2>
          <div v-for="prov in providers" :key="prov.name" class="rounded-2xl border border-amber-100/10 bg-white/[0.02] p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-medium text-stone-300">
                {{ prov.display_name || prov.name }}
                <span
                  class="ml-2 text-xs px-2 py-0.5 rounded-full"
                  :class="getProviderStatus(prov.name) === 'ok'
                    ? 'bg-green-500/10 text-green-300'
                    : getProviderStatus(prov.name) === 'disconnected'
                    ? 'bg-stone-500/10 text-stone-400'
                    : 'bg-rose-500/10 text-rose-300'"
                >
                  {{ providerStatusLabel(prov.name) }}
                </span>
              </h3>
              <div class="flex items-center gap-2">
                <button
                  @click="testProvider(prov.name)"
                  :disabled="providerStatuses[prov.name] === 'testing'"
                  class="text-xs text-amber-400 hover:text-amber-300 transition disabled:opacity-50"
                >
                  {{ providerStatuses[prov.name] === 'testing' ? '...' : t('modelsPage.testConnection') }}
                </button>
              </div>
            </div>

            <!-- Ollama Provider → 显示本地模型 -->
            <template v-if="prov.name === 'ollama'">
              <div v-if="ollamaConnected && settingsStore.ollamaModels.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                <button
                  v-for="mod in settingsStore.ollamaModels"
                  :key="mod"
                  @click="selectOllama(mod)"
                  class="rounded-xl px-3 py-2 text-sm text-left font-medium border transition"
                  :class="isCurrentOllama(mod)
                    ? 'bg-amber-500 text-stone-950 shadow-[0_12px_30px_rgba(217,119,6,0.25)]'
                    : 'border-amber-100/10 bg-white/[0.04] text-stone-200 hover:border-amber-300/25 hover:bg-amber-500/10'"
                >
                  {{ mod }}
                </button>
              </div>
              <div v-else class="text-xs text-stone-500">
                {{ ollamaConnected ? t('modelsPage.noModelsHint') : t('modelsPage.ollamaDisconnected') }}
              </div>
            </template>

            <!-- OpenAI Compatible Provider → 显示端点模型 -->
            <template v-else-if="prov.name === 'openai_compat'">
              <div v-if="settingsStore.endpoints.length > 0" class="space-y-3">
                <div v-for="ep in settingsStore.endpoints" :key="ep.id" class="rounded-xl border border-amber-100/10 bg-[#14110f]/60 p-4">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-medium text-stone-300">
                      {{ ep.name }}
                      <span v-if="!ep.enabled" class="ml-2 text-xs text-stone-500">({{ t('common.disabled') }})</span>
                    </h4>
                    <div class="flex items-center gap-2">
                      <button
                        @click="fetchModels(ep.id)"
                        :disabled="busyEndpointId === ep.id"
                        class="text-xs text-amber-400 hover:text-amber-300 transition disabled:opacity-50"
                      >
                        {{ busyEndpointId === ep.id ? '...' : t('modelsPage.fetchModels') }}
                      </button>
                      <button @click="openEdit(ep)" class="text-xs text-stone-400 hover:text-stone-200 transition">
                        {{ t('common.edit') }}
                      </button>
                      <button @click="removeEndpoint(ep.id)" class="text-xs text-stone-400 hover:text-rose-400 transition">
                        {{ t('common.delete') }}
                      </button>
                    </div>
                  </div>

                  <!-- 模型列表 -->
                  <div v-if="ep.models && ep.models.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-1.5">
                    <button
                      v-for="mod in ep.models"
                      :key="ep.id + '-' + mod"
                      :disabled="!ep.enabled"
                      @click="selectRemote(ep, mod)"
                      class="rounded-xl px-3 py-1.5 text-xs font-medium border transition text-left"
                      :class="isCurrentRemote(ep, mod)
                        ? 'bg-amber-500 text-stone-950'
                        : 'border-amber-100/10 bg-white/[0.04] text-stone-200 hover:border-amber-300/25 hover:bg-amber-500/10 disabled:opacity-40 disabled:cursor-not-allowed'"
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
              <div v-else class="text-xs text-stone-500">{{ t('modelsPage.noEndpoints') }}</div>
            </template>

            <!-- 其他 Provider → 简洁显示 -->
            <template v-else>
              <p class="text-xs text-stone-500">{{ prov.auth_type === 'none' ? t('modelsPage.noAuthNeeded') : t('modelsPage.configuredInSettings') }}</p>
            </template>
          </div>
        </section>

        <!-- 添加端点按钮 -->
        <section class="flex items-center gap-3">
          <button
            @click="showAddEndpoint = true"
            class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-5 py-3 text-sm font-medium text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
          >
            + {{ t('modelsPage.createEndpoint') }}
          </button>
        </section>

        <!-- 添加端点弹窗 -->
        <div
          v-if="showAddEndpoint"
          class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
          @click.self="showAddEndpoint = false"
        >
          <div class="w-full max-w-md rounded-[28px] border border-amber-100/10 bg-[#171411] p-5 shadow-[0_30px_100px_rgba(8,7,5,0.65)]">
            <h3 class="mb-4 text-lg font-semibold text-stone-100">{{ t('modelsPage.createEndpoint') }}</h3>
            <div class="space-y-3">
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
            </div>
            <div class="mt-5 flex justify-end gap-2">
              <button type="button" @click="showAddEndpoint = false" class="px-3 py-2 text-sm text-stone-400 transition hover:text-stone-100">
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
        </div>
      </div>
    </main>

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
