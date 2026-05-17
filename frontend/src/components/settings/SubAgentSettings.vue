<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useI18n } from '@/i18n'

const settingsStore = useSettingsStore()
const editingAgent = ref<string | null>(null)
const localConfigs = ref<Record<string, any>>({})
const { t } = useI18n()

const subagents = computed(() => {
  const result = []
  for (const [type, agent] of Object.entries(settingsStore.subagents)) {
    const config = localConfigs.value[type] || {}
    result.push({
      ...agent,
      type,
      ...config
    })
  }
  return result
})

const agentIcons: Record<string, string> = {
  code: 'code',
  writing: 'edit-3',
  data: 'bar-chart-2',
  research: 'search',
  plan: 'list-checks'
}

const getIconPath = (iconName: string) => {
  const icons: Record<string, string> = {
    'code': 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
    'edit-3': 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4',
    'bar-chart-2': 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    'search': 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7',
    'list-checks': 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4'
  }
  return icons[iconName] || icons['search']
}

const startEdit = (agentType: string) => {
  editingAgent.value = agentType
  const agent = settingsStore.subagents[agentType]
  if (agent) {
    localConfigs.value[agentType] = { ...agent }
  }
}

const saveAgent = async (agentType: string) => {
  const config = localConfigs.value[agentType]
  if (config) {
    await settingsStore.updateSubagent(agentType, config)
    editingAgent.value = null
    delete localConfigs.value[agentType]
  }
}

const cancelEdit = (agentType: string) => {
  editingAgent.value = null
  delete localConfigs.value[agentType]
}
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <div class="bg-slate-800 rounded-xl p-6">
      <h2 class="text-xl font-semibold text-white mb-6">{{ t('settings.subagentsTitle') }}</h2>
      
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="agent in subagents"
          :key="agent.type"
          class="bg-slate-700 rounded-xl p-5"
          :class="{ 'ring-2 ring-blue-500': editingAgent === agent.type }"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="getIconPath(agentIcons[agent.type] || 'search')" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-white">{{ agent.name }}</h3>
                <p class="text-sm text-slate-400">{{ agent.type }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span
                class="px-2 py-1 rounded-full text-xs font-medium"
                :class="agent.enabled ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'"
              >
                {{ agent.enabled ? t('common.enabled') : t('common.disabled') }}
              </span>
            </div>
          </div>
          
          <p class="text-sm text-slate-400 mb-4">{{ agent.description }}</p>
          
          <div v-if="editingAgent === agent.type" class="space-y-3">
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('settings.subagentsModelLabel') }}</label>
              <input
                v-model="localConfigs[agent.type].llm_model"
                class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                :placeholder="t('settings.subagentsInheritPlaceholder')"
              />
            </div>
            
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('settings.subagentsTemperature') }}: {{ localConfigs[agent.type].temperature.toFixed(1) }}</label>
              <input
                type="range"
                v-model.number="localConfigs[agent.type].temperature"
                min="0"
                max="1"
                step="0.1"
                class="w-full h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('settings.subagentsPersonalityWeight') }}: {{ localConfigs[agent.type].personality_weight.toFixed(1) }}</label>
              <input
                type="range"
                v-model.number="localConfigs[agent.type].personality_weight"
                min="0"
                max="1"
                step="0.1"
                class="w-full h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-300">{{ t('common.enabled') }}</span>
              <button
                @click="localConfigs[agent.type].enabled = !localConfigs[agent.type].enabled"
                class="w-12 h-6 rounded-full transition-colors"
                :class="localConfigs[agent.type].enabled ? 'bg-blue-600' : 'bg-slate-600'"
              >
                <span
                  class="block w-5 h-5 bg-white rounded-full shadow transition-transform"
                  :class="localConfigs[agent.type].enabled ? 'translate-x-6' : 'translate-x-0.5'"
                ></span>
              </button>
            </div>
            
            <div class="flex gap-2">
              <button
                @click="saveAgent(agent.type)"
                class="flex-1 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm font-medium transition-colors"
              >
                {{ t('common.save') }}
              </button>
              <button
                @click="cancelEdit(agent.type)"
                class="flex-1 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg text-white text-sm font-medium transition-colors"
              >
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
          
          <div v-else>
            <div class="grid grid-cols-2 gap-2 text-sm mb-4">
              <div class="bg-slate-600/50 rounded-lg p-2">
                <span class="text-slate-400">{{ t('common.model') }}:</span>
                <span class="text-white ml-1">{{ agent.llm_model || t('settings.subagentsInheritValue') }}</span>
              </div>
              <div class="bg-slate-600/50 rounded-lg p-2">
                <span class="text-slate-400">{{ t('settings.subagentsTemperatureShort') }}:</span>
                <span class="text-white ml-1">{{ agent.temperature.toFixed(1) }}</span>
              </div>
            </div>
            
            <button
              @click="startEdit(agent.type)"
              class="w-full py-2 bg-slate-600 hover:bg-slate-500 rounded-lg text-white text-sm font-medium transition-colors"
            >
              {{ t('settings.subagentsEdit') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
