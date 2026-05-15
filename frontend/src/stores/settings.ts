import { defineStore } from 'pinia'
import { ref } from 'vue'
import { personalityApi, subagentApi, modelApi } from '@/api'
import type { Personality, SubAgent, Endpoint, ModelsOverviewResponse } from '@/types'

const STORAGE_KEY = 'tars_settings'

interface StoredSettings {
  provider?: 'ollama' | 'openai_compatible'
  endpoint_id?: string | null
  model?: string
  /** @deprecated 迁移用 */
  currentModel?: string
  /** @deprecated 迁移用 */
  currentProvider?: string
}

export const useSettingsStore = defineStore('settings', () => {
  const personality = ref<Personality | null>(null)
  const subagents = ref<Record<string, SubAgent>>({})
  const loading = ref(false)

  const ollamaModels = ref<string[]>([])
  const ollamaBaseUrl = ref('')
  const ollamaStatus = ref('disconnected')
  const endpoints = ref<Endpoint[]>([])
  const currentModel = ref('')
  const currentProvider = ref<'ollama' | 'openai_compatible'>('ollama')
  const currentEndpointId = ref<string | null>(null)

  const _loadFromStorage = (): StoredSettings => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const raw = JSON.parse(stored) as StoredSettings
        if (!raw.provider && raw.currentProvider) {
          if (raw.currentProvider === 'ollama') {
            raw.provider = 'ollama'
          } else if (raw.currentProvider.startsWith('custom:')) {
            raw.provider = 'openai_compatible'
            raw.endpoint_id = raw.currentProvider.slice('custom:'.length)
          }
        }
        if (!raw.model && raw.currentModel) {
          raw.model = raw.currentModel
        }
        return raw
      }
    } catch {
      /* ignore */
    }
    return {}
  }

  const _saveToStorage = () => {
    try {
      const settings: StoredSettings = {
        provider: currentProvider.value,
        endpoint_id: currentEndpointId.value,
        model: currentModel.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {
      /* ignore */
    }
  }

  const _applyOverview = (data: ModelsOverviewResponse) => {
    ollamaModels.value = data.ollama_models || []
    ollamaBaseUrl.value = data.ollama_base_url || ''
    ollamaStatus.value = data.ollama_status || 'disconnected'
    endpoints.value = data.endpoints || []
    currentModel.value = data.current?.model || ''
    currentProvider.value = data.current?.provider || 'ollama'
    currentEndpointId.value = data.current?.endpoint_id ?? null
  }

  const loadPersonality = async () => {
    loading.value = true
    try {
      const response = await personalityApi.getPersonality()
      if (response.success && response.data) {
        personality.value = response.data
      }
    } catch {
      personality.value = null
    } finally {
      loading.value = false
    }
  }

  const updatePersonality = async (data: {
    parameters?: Partial<Personality['parameters']>
    communication_style?: string
    behavior_rules?: string[]
  }) => {
    loading.value = true
    try {
      const response = await personalityApi.updatePersonality(data)
      if (response.success && response.data) {
        personality.value = response.data
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const loadSubagents = async () => {
    loading.value = true
    try {
      const response = await subagentApi.getSubagents()
      subagents.value = response.subagents
    } catch {
      subagents.value = {}
    } finally {
      loading.value = false
    }
  }

  const updateSubagent = async (agentType: string, config: Partial<SubAgent>) => {
    loading.value = true
    try {
      const response = await subagentApi.updateSubagent(agentType, config)
      if (response.success) {
        await loadSubagents()
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const applyModelSelection = async (
    provider: 'ollama' | 'openai_compatible',
    model: string,
    endpointId?: string | null
  ) => {
    loading.value = true
    try {
      const res = await modelApi.switchModel({
        provider,
        model,
        endpoint_id: provider === 'openai_compatible' ? endpointId ?? undefined : undefined,
      })
      if (res.success && res.current) {
        currentModel.value = res.current.model
        currentProvider.value = res.current.provider
        currentEndpointId.value = res.current.endpoint_id ?? null
        _saveToStorage()
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const loadModels = async () => {
    loading.value = true
    try {
      const data = await modelApi.getModelsOverview()
      _applyOverview(data)

      const stored = _loadFromStorage()
      const wantModel = stored.model
      const wantProvider = stored.provider
      const wantEp = stored.endpoint_id ?? null
      const cur = data.current
      const differs =
        wantModel &&
        wantProvider &&
        (wantModel !== cur?.model ||
          wantProvider !== cur?.provider ||
          wantEp !== (cur?.endpoint_id ?? null))
      if (differs) {
        const ok = await applyModelSelection(wantProvider, wantModel, wantEp)
        if (ok) {
          const again = await modelApi.getModelsOverview()
          _applyOverview(again)
        }
      }
    } catch (e) {
      console.error('loadModels failed', e)
    } finally {
      loading.value = false
    }
  }

  const switchModel = async (modelName: string) => {
    return applyModelSelection('ollama', modelName)
  }

  const createEndpoint = async (payload: { name: string; base_url: string; api_key?: string }) => {
    const ep = await modelApi.createEndpoint(payload)
    const rest = endpoints.value.filter((e) => e.id !== ep.id)
    endpoints.value = [ep, ...rest]
    void loadModels().catch((err) => console.warn('loadModels after createEndpoint', err))
    return ep
  }

  const updateEndpoint = async (
    id: string,
    payload: Partial<{
      name: string
      base_url: string
      api_key: string
      models: string[]
      enabled: boolean
    }>
  ) => {
    const ep = await modelApi.updateEndpoint(id, payload)
    const i = endpoints.value.findIndex((e) => e.id === ep.id)
    if (i >= 0) {
      endpoints.value[i] = ep
    }
    void loadModels().catch((err) => console.warn('loadModels after updateEndpoint', err))
    return ep
  }

  const deleteEndpoint = async (id: string) => {
    await modelApi.deleteEndpoint(id)
    endpoints.value = endpoints.value.filter((e) => e.id !== id)
    void loadModels().catch((err) => console.warn('loadModels after deleteEndpoint', err))
  }

  const fetchEndpointModels = async (id: string) => {
    return modelApi.fetchEndpointModels(id)
  }

  const testEndpoint = async (id: string) => {
    return modelApi.testEndpoint(id)
  }

  const initSettings = async () => {
    await Promise.all([loadPersonality(), loadSubagents(), loadModels()])
  }

  return {
    personality,
    subagents,
    loading,
    ollamaModels,
    ollamaBaseUrl,
    ollamaStatus,
    endpoints,
    currentModel,
    currentProvider,
    currentEndpointId,
    loadPersonality,
    updatePersonality,
    loadSubagents,
    updateSubagent,
    loadModels,
    applyModelSelection,
    switchModel,
    createEndpoint,
    updateEndpoint,
    deleteEndpoint,
    fetchEndpointModels,
    testEndpoint,
    initSettings,
  }
})
