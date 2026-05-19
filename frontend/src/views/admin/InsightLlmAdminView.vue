<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { biApi, insightApi, type InsightLlmSettingsPayload } from '@/api'
import type { DataSource, Endpoint } from '@/types'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'

const { t } = useI18n()
const toast = useToast()

const pageLoading = ref(true)
const llmSaving = ref(false)
const profiling = ref(false)
const profilingMessage = ref('')
const datasources = ref<DataSource[]>([])
const selectedDsId = ref('')
const effectiveLabel = ref('—')
const chatCurrentLabel = ref('')

const llmForm = ref<InsightLlmSettingsPayload>({
  use_chat_default: true,
  provider: 'ollama',
  model: '',
  endpoint_id: null,
})

const ollamaModels = ref<string[]>([])
const endpoints = ref<Endpoint[]>([])

const modelChoices = computed(() => {
  if (llmForm.value.use_chat_default) return []
  if (llmForm.value.provider === 'ollama') return ollamaModels.value
  const ep = endpoints.value.find((e) => e.id === llmForm.value.endpoint_id)
  return ep?.models || []
})

function onProviderChange() {
  llmForm.value.model = ''
  if (llmForm.value.provider === 'openai_compatible' && !llmForm.value.endpoint_id) {
    llmForm.value.endpoint_id = endpoints.value[0]?.id || null
  }
}

function onEndpointChange() {
  llmForm.value.model = ''
}

async function loadPage() {
  pageLoading.value = true
  try {
    const [dsRes, settingsRes, optionsRes] = await Promise.all([
      biApi.listDataSources(),
      insightApi.getLlmSettings(),
      insightApi.getLlmOptions(),
    ])
    datasources.value = dsRes.datasources
    if (!selectedDsId.value && datasources.value.length) {
      selectedDsId.value = datasources.value[0].id
    }
    ollamaModels.value = optionsRes.ollama_models || []
    endpoints.value = optionsRes.endpoints || []
    const s = settingsRes.settings
    llmForm.value = {
      use_chat_default: s.use_chat_default,
      provider: s.provider || 'ollama',
      model: s.model || '',
      endpoint_id: s.endpoint_id ?? null,
    }
    effectiveLabel.value = settingsRes.effective?.label || '—'
    const cc = settingsRes.chat_current
    chatCurrentLabel.value = cc?.label || cc?.model || ''
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('insight.loadFailed')))
  } finally {
    pageLoading.value = false
  }
}

async function saveLlmSettings() {
  llmSaving.value = true
  try {
    const res = await insightApi.saveLlmSettings({ ...llmForm.value })
    effectiveLabel.value = res.effective?.label || effectiveLabel.value
    toast.success(t('insight.llmSaved'))
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('insight.llmSaveFailed')))
  } finally {
    llmSaving.value = false
  }
}

async function waitForProfileRun(runId: string, maxWaitMs = 600_000) {
  const deadline = Date.now() + maxWaitMs
  while (Date.now() < deadline) {
    const run = await insightApi.getProfileRun(runId)
    const progress = run.progress as { message?: string } | undefined
    profilingMessage.value = t('insight.profilingProgress', {
      message: progress?.message || run.status || '…',
    })
    if (run.status === 'completed' || run.status === 'failed') return
    await new Promise((r) => setTimeout(r, 2000))
  }
}

async function runProfileWithLlm() {
  if (!selectedDsId.value) {
    toast.error(t('insight.pickDatasource'))
    return
  }
  profiling.value = true
  profilingMessage.value = t('insight.profilingProgress', { message: '…' })
  try {
    await insightApi.saveLlmSettings({ ...llmForm.value })
    const res = await insightApi.startForge(selectedDsId.value, {
      force: true,
      llm: { ...llmForm.value, persist: true },
    })
    await waitForProfileRun(res.run_id)
    toast.success(t('insight.llmSavedNeedProfile'))
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('bi.insightProfileFailed')))
  } finally {
    profiling.value = false
    profilingMessage.value = ''
  }
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <div class="max-w-3xl space-y-6 text-stone-200">
    <div>
      <h2 class="text-lg font-semibold text-stone-100">{{ t('insight.llmTitle') }}</h2>
      <p class="mt-1 text-sm text-stone-400">{{ t('insight.adminLlmIntro') }}</p>
    </div>

    <div v-if="pageLoading" class="text-sm text-stone-500">{{ t('insight.loading') }}</div>

    <template v-else>
      <p class="text-sm text-stone-400">{{ t('insight.llmHint') }}</p>

      <label class="flex items-center gap-2 text-sm cursor-pointer">
        <input v-model="llmForm.use_chat_default" type="radio" :value="true" />
        {{ t('insight.llmUseChat') }}
        <span v-if="chatCurrentLabel" class="text-indigo-300">（{{ chatCurrentLabel }}）</span>
      </label>
      <label class="flex items-center gap-2 text-sm cursor-pointer">
        <input v-model="llmForm.use_chat_default" type="radio" :value="false" />
        {{ t('insight.llmCustom') }}
      </label>

      <div v-if="!llmForm.use_chat_default" class="grid gap-3 pl-1">
        <div>
          <label class="text-xs text-stone-500">{{ t('insight.llmProvider') }}</label>
          <select
            v-model="llmForm.provider"
            class="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
            @change="onProviderChange"
          >
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">{{ t('insight.llmRemote') }}</option>
          </select>
        </div>
        <div v-if="llmForm.provider === 'openai_compatible'">
          <label class="text-xs text-stone-500">{{ t('insight.llmEndpoint') }}</label>
          <select
            v-model="llmForm.endpoint_id"
            class="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
            @change="onEndpointChange"
          >
            <option :value="null">{{ t('insight.llmPickEndpoint') }}</option>
            <option v-for="ep in endpoints" :key="ep.id" :value="ep.id">{{ ep.name }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-stone-500">{{ t('insight.llmModel') }}</label>
          <select
            v-model="llmForm.model"
            class="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
          >
            <option value="">{{ t('insight.llmPickModel') }}</option>
            <option v-for="m in modelChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
      </div>

      <p class="text-sm">
        {{ t('insight.llmEffective') }}：<strong class="text-stone-100">{{ effectiveLabel }}</strong>
      </p>

      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-lg border border-stone-600 px-4 py-2 text-sm hover:bg-stone-800 disabled:opacity-50"
          :disabled="llmSaving || profiling"
          @click="saveLlmSettings"
        >
          {{ llmSaving ? t('insight.llmSaving') : t('insight.llmSave') }}
        </button>
      </div>

      <hr class="border-stone-800" />

      <div>
        <label class="text-xs text-stone-500">{{ t('insight.selectDatasource') }}</label>
        <select
          v-model="selectedDsId"
          class="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
        >
          <option value="">{{ t('insight.selectDatasource') }}</option>
          <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
            {{ ds.name }} ({{ ds.db_type }})
          </option>
        </select>
      </div>

      <button
        type="button"
        class="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
        :disabled="!selectedDsId || profiling"
        @click="runProfileWithLlm"
      >
        {{ profiling ? profilingMessage || t('bi.insightProfiling') : t('insight.runProfile') }}
      </button>
    </template>
  </div>
</template>
