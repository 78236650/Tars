<script setup lang="ts">
import { ref, computed } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
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
  code: 'lucide:code',
  writing: 'lucide:edit-3',
  data: 'lucide:bar-chart-3',
  research: 'lucide:search',
  plan: 'lucide:list-checks'
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
                <BaseIcon :icon="agentIcons[agent.type] || 'lucide:search'" :size="24" class="text-white" />
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
