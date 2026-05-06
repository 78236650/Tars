import { defineStore } from 'pinia'
import { ref } from 'vue'
import { personalityApi, subagentApi, modelApi } from '@/api'
import type { Personality, SubAgent } from '@/types'

const STORAGE_KEY = 'tars_settings'

interface StoredSettings {
  currentModel?: string
  currentProvider?: string
}

export const useSettingsStore = defineStore('settings', () => {
  const personality = ref<Personality | null>(null)
  const subagents = ref<Record<string, SubAgent>>({})
  const availableModels = ref<string[]>([])
  const currentModel = ref('')
  const currentProvider = ref('ollama')
  const customModels = ref<any[]>([])
  const loading = ref(false)

  const _loadFromStorage = (): StoredSettings => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        return JSON.parse(stored)
      }
    } catch {}
    return {}
  }

  const _saveToStorage = () => {
    try {
      const settings: StoredSettings = {
        currentModel: currentModel.value,
        currentProvider: currentProvider.value
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {}
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

  const loadModels = async () => {
    loading.value = true
    try {
      const response = await modelApi.getModels()
      availableModels.value = response.models

      const stored = _loadFromStorage()
      currentModel.value = response.current_model || stored.currentModel || ''
      currentProvider.value = response.current_provider || stored.currentProvider || 'ollama'

      if (stored.currentModel && stored.currentModel !== response.current_model) {
        const result = await modelApi.switchModel(stored.currentModel)
        if (result.success) {
          currentModel.value = stored.currentModel
        }
      }

      // 获取自定义模型列表
      try {
        const customRes = await fetch('/api/models/custom')
        if (customRes.ok) {
          customModels.value = await customRes.json()
        }
      } catch {
        customModels.value = []
      }
    } catch {
      availableModels.value = []
      currentModel.value = ''
      currentProvider.value = 'ollama'
    } finally {
      loading.value = false
    }
  }

  const switchModel = async (modelName: string) => {
    loading.value = true
    try {
      const response = await modelApi.switchModel(modelName)
      if (response.success) {
        currentModel.value = modelName
        currentProvider.value = 'ollama'
        _saveToStorage()
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const switchCustomModel = async (modelId: string) => {
    loading.value = true
    try {
      const response = await fetch(`/api/models/switch-custom/${modelId}`, {
        method: 'POST'
      })
      const data = await response.json()

      if (data.success) {
        currentModel.value = data.current_model
        currentProvider.value = data.current_provider
        _saveToStorage()
        return { success: true, message: data.message }
      } else {
        return { success: false, message: data.detail || '切换失败' }
      }
    } catch (error) {
      console.error('切换模型失败:', error)
      return { success: false, message: '网络错误' }
    } finally {
      loading.value = false
    }
  }

  const initSettings = async () => {
    await Promise.all([
      loadPersonality(),
      loadSubagents(),
      loadModels()
    ])
  }

  return {
    personality,
    subagents,
    availableModels,
    currentModel,
    currentProvider,
    customModels,
    loading,
    loadPersonality,
    updatePersonality,
    loadSubagents,
    updateSubagent,
    loadModels,
    switchModel,
    switchCustomModel,
    initSettings
  }
})