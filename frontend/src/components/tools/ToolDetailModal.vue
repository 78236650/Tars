<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { skillsApi } from '@/api'
import { useI18n } from '@/i18n'

const props = defineProps<{
  tool: {
    id: string
    name: string
    icon?: string
    type: string
    source?: string
    status?: string
    description: string
    usage?: string
    config?: Record<string, any>
    default_config?: Record<string, any>
    // Skill fields
    prompt_template?: string
    parameters?: { name: string; type: string; description: string; required: boolean; default?: any }[]
    version?: string
    author?: string
    tags?: string[]
    permissions?: string[]
    enabled?: boolean
  }
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()

const loading = ref(false)
const message = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const isSkill = computed(() => props.tool.type === 'plugin' || props.tool.type === 'prompt')
const isPromptSkill = computed(() => props.tool.type === 'prompt')
const isEnabled = computed(() => props.tool.enabled !== false && props.tool.status !== 'disabled')

const typeLabel = computed(() => {
  switch (props.tool.type) {
    case 'builtin': return t('toolDetail.builtin')
    case 'plugin': return t('toolDetail.plugin')
    case 'prompt': return t('toolDetail.prompt')
    default: return props.tool.type
  }
})

const typeClass = computed(() => {
  switch (props.tool.type) {
    case 'builtin': return 'bg-blue-600/20 text-blue-400'
    case 'plugin': return 'bg-green-600/20 text-green-400'
    case 'prompt': return 'bg-purple-600/20 text-purple-400'
    default: return 'bg-slate-600/20 text-slate-400'
  }
})

const toggleEnabled = async () => {
  loading.value = true
  message.value = null
  try {
    if (isEnabled.value) {
      await skillsApi.disableSkill(props.tool.id)
      message.value = { type: 'success', text: t('toolDetail.disabledMsg') }
    } else {
      await skillsApi.enableSkill(props.tool.id)
      message.value = { type: 'success', text: t('toolDetail.enabledMsg') }
    }
    setTimeout(() => emit('close'), 800)
  } catch (e) {
    message.value = { type: 'error', text: t('toolDetail.operationFailed') }
  } finally {
    loading.value = false
  }
}

const deleteSkill = async () => {
  if (!confirm(t('toolDetail.uninstallConfirm'))) return
  loading.value = true
  try {
    await skillsApi.deleteSkill(props.tool.id)
    message.value = { type: 'success', text: t('toolDetail.uninstalled') }
    setTimeout(() => emit('close'), 800)
  } catch (e: any) {
    message.value = { type: 'error', text: t('toolDetail.operationFailed') }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="emit('close')"></div>

    <div class="relative bg-slate-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div class="flex items-center gap-3">
          <span class="text-3xl">{{ tool.icon || '🔧' }}</span>
          <div>
            <h2 class="text-xl font-semibold text-white">{{ tool.name }}</h2>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-xs px-2 py-0.5 rounded-full" :class="typeClass">{{ typeLabel }}</span>
              <span v-if="tool.version" class="text-xs text-slate-500">v{{ tool.version }}</span>
              <span v-if="tool.author" class="text-xs text-slate-500">by {{ tool.author }}</span>
            </div>
          </div>
        </div>
        <button @click="emit('close')" class="p-2 hover:bg-slate-700 rounded-lg transition-colors">
          <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5">
        <!-- 描述 -->
        <div>
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.description') }}</h3>
          <p class="text-white">{{ tool.description }}</p>
        </div>

        <!-- 标签 -->
        <div v-if="tool.tags && tool.tags.length > 0">
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.tags') }}</h3>
          <div class="flex flex-wrap gap-2">
            <span v-for="tag in tool.tags" :key="tag" class="px-2 py-1 bg-slate-700 text-slate-300 rounded text-xs">{{ tag }}</span>
          </div>
        </div>

        <!-- Prompt 模板（仅 PromptSkill） -->
        <div v-if="isPromptSkill && tool.prompt_template">
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.promptTemplate') }}</h3>
          <pre class="bg-slate-900 rounded-lg p-4 text-slate-300 text-sm overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap">{{ tool.prompt_template }}</pre>
        </div>

        <!-- 参数 -->
        <div v-if="tool.parameters && tool.parameters.length > 0">
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.parameters') }}</h3>
          <div class="space-y-2">
            <div v-for="param in tool.parameters" :key="param.name" class="bg-slate-900 rounded-lg p-3">
              <div class="flex items-center gap-2">
                <span class="text-white font-mono text-sm">{{ param.name }}</span>
                <span class="text-xs px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">{{ param.type }}</span>
                <span v-if="param.required" class="text-xs text-red-400">{{ t('toolDetail.required') }}</span>
              </div>
              <p v-if="param.description" class="text-sm text-slate-400 mt-1">{{ param.description }}</p>
              <p v-if="param.default !== undefined && param.default !== null" class="text-xs text-slate-500 mt-1">{{ t('toolDetail.defaultValue') }}: {{ param.default }}</p>
            </div>
          </div>
        </div>

        <!-- 权限声明 -->
        <div v-if="tool.permissions && tool.permissions.length > 0">
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.permissions') }}</h3>
          <div class="flex flex-wrap gap-2">
            <span v-for="perm in tool.permissions" :key="perm" class="px-2 py-1 bg-yellow-900/30 text-yellow-400 border border-yellow-700 rounded text-xs">{{ perm }}</span>
          </div>
        </div>

        <!-- 使用方法（内置工具） -->
        <div v-if="tool.usage">
          <h3 class="text-sm font-medium text-slate-400 mb-2">{{ t('toolDetail.usage') }}</h3>
          <pre class="bg-slate-900 rounded-lg p-4 text-slate-300 text-sm overflow-x-auto">{{ tool.usage }}</pre>
        </div>

        <!-- 消息提示 -->
        <div v-if="message" class="p-3 rounded-lg" :class="message.type === 'success' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'">
          {{ message.text }}
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-slate-700 flex items-center justify-between">
        <button
          v-if="isSkill && tool.source !== 'builtin'"
          @click="deleteSkill"
          :disabled="loading"
          class="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-colors disabled:opacity-50"
        >{{ t('common.uninstall') }}</button>
        <div v-else></div>

        <button
          v-if="isSkill"
          @click="toggleEnabled"
          :disabled="loading"
          class="px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
          :class="isEnabled ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white'"
        >{{ isEnabled ? t('common.disable') : t('common.enable') }}</button>
      </div>
    </div>
  </div>
</template>
