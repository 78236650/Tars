<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'

const settingsStore = useSettingsStore()
const toast = useToast()
const { t } = useI18n()

const loading = ref(false)
const testing = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)

const customModels = ref<any[]>([])
const showAddForm = ref(false)
const editingModel = ref<any>(null)
const addForm = ref({
  name: '',
  base_url: '',
  model: '',
  api_key: '',
  description: ''
})

const providerTypes = computed(() => [
  { type: 'ollama', name: t('models.ollama'), icon: '💻', description: t('models.ollamaDesc') },
  { type: 'openrouter', name: t('models.openrouter'), icon: '🌐', description: t('models.openrouterDesc') },
  { type: 'anthropic', name: t('models.anthropic'), icon: '🤖', description: t('models.anthropicDesc') },
  { type: 'openai', name: t('models.openai'), icon: '🚀', description: t('models.openaiDesc') }
])

const selectedProvider = ref('ollama')

const providerConfigs = ref<Record<string, any>>({
  ollama: {
    type: 'ollama',
    name: t('models.ollama'),
    base_url: 'http://localhost:11434',
    default_model: 'llama3.2',
    enabled: true
  },
  openrouter: {
    type: 'openrouter',
    name: 'OpenRouter',
    base_url: 'https://openrouter.ai/api/v1',
    api_key: '',
    default_model: 'anthropic/claude-sonnet-4',
    enabled: false
  },
  anthropic: {
    type: 'anthropic',
    name: 'Anthropic (Claude)',
    base_url: 'https://api.anthropic.com',
    api_key: '',
    default_model: 'claude-sonnet-4-20250514',
    enabled: false
  },
  openai: {
    type: 'openai',
    name: 'OpenAI (GPT)',
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    default_model: 'gpt-4o',
    enabled: false
  }
})

const currentConfig = computed(() => providerConfigs.value[selectedProvider.value])

const loadCustomModels = async () => {
  try {
    const response = await fetch('/api/models/custom')
    if (response.ok) {
      customModels.value = await response.json()
    }
  } catch (error) {
    console.error('加载自定义模型失败:', error)
  }
}

const addCustomModel = async () => {
  if (!addForm.value.name || !addForm.value.base_url || !addForm.value.model) {
    testResult.value = { success: false, message: t('addSkill.fillRequired') }
    return
  }
  loading.value = true
  try {
    const response = await fetch('/api/models/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(addForm.value)
    })
    if (response.ok) {
      await loadCustomModels()
      showAddForm.value = false
      addForm.value = { name: '', base_url: '', model: '', api_key: '', description: '' }
      testResult.value = { success: true, message: t('common.success') }
    } else {
      throw new Error(t('common.error'))
    }
  } catch (error) {
    testResult.value = { success: false, message: t('common.error') }
  } finally {
    loading.value = false
  }
}

const deleteCustomModel = async (id: string) => {
  if (!confirm(t('toolDetail.uninstallConfirm'))) return
  loading.value = true
  try {
    const response = await fetch(`/api/models/custom/${id}`, { method: 'DELETE' })
    if (response.ok) {
      await loadCustomModels()
      testResult.value = { success: true, message: t('common.success') }
    }
  } catch (error) {
    testResult.value = { success: false, message: t('common.error') }
  } finally {
    loading.value = false
  }
}

const testCustomModel = async (id: string) => {
  testing.value = true
  testResult.value = null
  try {
    const response = await fetch(`/api/models/custom/${id}/test`, { method: 'POST' })
    testResult.value = await response.json()
  } catch (error) {
    testResult.value = { success: false, message: t('common.error') }
  } finally {
    testing.value = false
  }
}

const switchToCustomModel = async (model: any) => {
  if (settingsStore.currentProvider === 'custom:' + model.id) return

  const confirmed = confirm(`确定要切换到模型 "${model.name}" 吗？\n\n频繁切换模型可能影响对话连贯性。`)
  if (!confirmed) return

  loading.value = true
  try {
    const result = await settingsStore.switchCustomModel(model.id)
    if (result.success) {
      toast.success(result.message)
    } else {
      toast.error(result.message)
    }
  } catch (error) {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    loading.value = false
  }
}

const loadConfig = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/models/providers')
    if (response.ok) {
      const data = await response.json()
      selectedProvider.value = data.current_provider
      data.providers.forEach((p: any) => {
        if (providerConfigs.value[p.type]) {
          providerConfigs.value[p.type] = { ...providerConfigs.value[p.type], ...p }
        }
      })
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  loading.value = true
  testResult.value = null
  try {
    const response = await fetch(`/api/models/providers/${selectedProvider.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(providerConfigs.value[selectedProvider.value])
    })
    if (response.ok) {
      toast.success(t('common.success'))
    } else {
      throw new Error(t('common.error'))
    }
  } catch (error) {
    toast.error(t('common.error'))
  } finally {
    loading.value = false
  }
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    const response = await fetch(`/api/models/providers/${selectedProvider.value}/test`, {
      method: 'POST'
    })
    const data = await response.json()
    testResult.value = data
  } catch (error) {
    testResult.value = { success: false, message: '测试失败: ' + error }
  } finally {
    testing.value = false
  }
}

const switchModel = async (modelName: string) => {
  if (settingsStore.currentModel === modelName) return

  const confirmed = confirm(`确定要切换到模型 "${modelName}" 吗？\n\n频繁切换模型可能影响对话连贯性。`)
  if (!confirmed) return

  loading.value = true
  try {
    const response = await fetch('/api/models/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_name: modelName,
        provider: selectedProvider.value
      })
    })
    if (response.ok) {
      await settingsStore.loadModels()
      toast.success(`已切换到模型: ${modelName}`)
    } else {
      throw new Error(t('sidebar.switchFailed'))
    }
  } catch (error) {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadConfig()
  settingsStore.loadModels()
  loadCustomModels()
})
</script>

<template>
  <div class="space-y-6">
    <div class="bg-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-medium text-white mb-4">选择 Provider</h3>

      <div class="grid grid-cols-2 gap-4">
        <button
          v-for="provider in providerTypes"
          :key="provider.type"
          @click="selectedProvider = provider.type"
          class="p-4 rounded-lg border-2 transition-all text-left"
          :class="selectedProvider === provider.type
            ? 'border-blue-500 bg-slate-700'
            : 'border-slate-700 bg-slate-800 hover:border-slate-600'"
        >
          <div class="flex items-center gap-3 mb-2">
            <span class="text-2xl">{{ provider.icon }}</span>
            <span class="text-white font-medium">{{ provider.name }}</span>
          </div>
          <p class="text-slate-400 text-sm">{{ provider.description }}</p>
        </button>
      </div>
    </div>

    <div class="bg-slate-800 rounded-xl p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-medium text-white">自定义模型</h3>
        <button
          @click="showAddForm = !showAddForm"
          class="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white text-sm transition-colors"
        >
          {{ showAddForm ? '取消' : '+ 添加模型' }}
        </button>
      </div>

      <div v-if="showAddForm" class="bg-slate-700 rounded-lg p-4 mb-4 space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">名称 *</label>
            <input
              v-model="addForm.name"
              type="text"
              placeholder="DeepSeek V3"
              class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">模型名称 *</label>
            <input
              v-model="addForm.model"
              type="text"
              placeholder="deepseek-chat"
              class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">API 地址 *</label>
          <input
            v-model="addForm.base_url"
            type="text"
            placeholder="https://api.deepseek.com/v1"
            class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">API Key</label>
          <input
            v-model="addForm.api_key"
            type="password"
            placeholder="sk-..."
            class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1">描述</label>
          <input
            v-model="addForm.description"
            type="text"
            placeholder="可选的描述信息"
            class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div class="flex gap-2">
          <button
            @click="addCustomModel"
            :disabled="loading"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors disabled:opacity-50"
          >
            {{ loading ? '添加中...' : '添加' }}
          </button>
        </div>
      </div>

      <div v-if="customModels.length === 0 && !showAddForm" class="text-center py-6 text-slate-400">
        暂无自定义模型，点击上方按钮添加
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="model in customModels"
          :key="model.id"
          class="bg-slate-700 rounded-lg p-4 flex items-center justify-between"
          :class="settingsStore.currentProvider === 'custom:' + model.id ? 'ring-2 ring-green-500' : ''"
        >
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="text-white font-medium">{{ model.name }}</span>
              <span class="px-2 py-0.5 bg-blue-600/30 text-blue-400 text-xs rounded">{{ model.model }}</span>
              <span v-if="settingsStore.currentProvider === 'custom:' + model.id" class="px-2 py-0.5 bg-green-600/30 text-green-400 text-xs rounded">使用中</span>
              <span v-else-if="!model.is_enabled" class="px-2 py-0.5 bg-red-600/30 text-red-400 text-xs rounded">已禁用</span>
            </div>
            <p class="text-sm text-slate-400 mt-1">{{ model.base_url }}</p>
            <p v-if="model.description" class="text-xs text-slate-500 mt-1">{{ model.description }}</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="testCustomModel(model.id)"
              :disabled="testing"
              class="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded text-white text-sm transition-colors"
            >
              测试
            </button>
            <button
              @click="switchToCustomModel(model)"
              :disabled="loading || !model.is_enabled"
              class="px-3 py-1.5 rounded text-white text-sm transition-colors"
              :class="settingsStore.currentProvider === 'custom:' + model.id ? 'bg-slate-600 cursor-default' : 'bg-blue-600 hover:bg-blue-700 disabled:opacity-50'"
            >
              {{ settingsStore.currentProvider === 'custom:' + model.id ? '使用中' : '使用' }}
            </button>
            <button
              @click="deleteCustomModel(model.id)"
              class="px-3 py-1.5 bg-red-600/30 hover:bg-red-600/50 rounded text-red-400 text-sm transition-colors"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-medium text-white mb-4">
        {{ providerTypes.find(p => p.type === selectedProvider)?.name }} 配置
      </h3>

      <div class="space-y-4">
        <template v-if="selectedProvider === 'ollama'">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              服务器地址
            </label>
            <input
              v-model="providerConfigs.ollama.base_url"
              type="text"
              placeholder="http://localhost:11434"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p class="text-xs text-slate-500 mt-1">默认: http://localhost:11434</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              默认模型
            </label>
            <input
              v-model="providerConfigs.ollama.default_model"
              type="text"
              placeholder="llama3.2"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p class="text-xs text-slate-500 mt-1">本地已安装的模型名称</p>
          </div>
        </template>

        <template v-else-if="selectedProvider === 'openrouter'">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              API Key
            </label>
            <input
              v-model="providerConfigs.openrouter.api_key"
              type="password"
              placeholder="sk-or-v1-..."
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p class="text-xs text-slate-500 mt-1">
              从 <a href="https://openrouter.ai/keys" target="_blank" class="text-blue-400 hover:underline">openrouter.ai/keys</a> 获取
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              默认模型
            </label>
            <select
              v-model="providerConfigs.openrouter.default_model"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="anthropic/claude-sonnet-4">Claude Sonnet 4</option>
              <option value="anthropic/claude-3.5-sonnet">Claude 3.5 Sonnet</option>
              <option value="openai/gpt-4o">GPT-4o</option>
              <option value="google/gemini-pro">Gemini Pro</option>
              <option value="meta-llama/llama-3-8b-instruct">Llama 3 8B</option>
            </select>
          </div>
        </template>

        <template v-else-if="selectedProvider === 'anthropic'">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              API Key
            </label>
            <input
              v-model="providerConfigs.anthropic.api_key"
              type="password"
              placeholder="sk-ant-..."
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p class="text-xs text-slate-500 mt-1">
              从 <a href="https://console.anthropic.com/settings/keys" target="_blank" class="text-blue-400 hover:underline">console.anthropic.com</a> 获取
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              默认模型
            </label>
            <select
              v-model="providerConfigs.anthropic.default_model"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
              <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
              <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku</option>
              <option value="claude-3-opus-20240229">Claude 3 Opus</option>
            </select>
          </div>
        </template>

        <template v-else-if="selectedProvider === 'openai'">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              API Key
            </label>
            <input
              v-model="providerConfigs.openai.api_key"
              type="password"
              placeholder="sk-..."
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p class="text-xs text-slate-500 mt-1">
              从 <a href="https://platform.openai.com/api-keys" target="_blank" class="text-blue-400 hover:underline">platform.openai.com</a> 获取
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              默认模型
            </label>
            <select
              v-model="providerConfigs.openai.default_model"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
            </select>
          </div>
        </template>
      </div>

      <div class="flex gap-3 mt-6">
        <button
          @click="testConnection"
          :disabled="testing"
          class="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors disabled:opacity-50"
        >
          {{ testing ? '测试中...' : '测试连接' }}
        </button>

        <button
          @click="saveConfig"
          :disabled="loading"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors disabled:opacity-50"
        >
          {{ loading ? '保存中...' : '保存配置' }}
        </button>
      </div>

      <div v-if="testResult" class="mt-4 p-3 rounded-lg" :class="testResult.success ? 'bg-green-900/50' : 'bg-red-900/50'">
        <p class="text-sm" :class="testResult.success ? 'text-green-400' : 'text-red-400'">
          {{ testResult.message }}
        </p>
      </div>
    </div>

    <div class="bg-slate-800 rounded-xl p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-medium text-white">可用模型</h3>
        <div class="text-sm text-slate-400">
          当前: <span class="text-blue-400">{{ settingsStore.currentModel }}</span>
        </div>
      </div>

      <div v-if="settingsStore.loading" class="text-center py-8 text-slate-400">
        加载中...
      </div>

      <div v-else-if="settingsStore.availableModels.length === 0" class="text-center py-8">
        <p class="text-slate-400 mb-2">未发现可用模型</p>
        <p class="text-sm text-slate-500">
          请确保 {{ providerTypes.find(p => p.type === selectedProvider)?.name }} 服务正在运行
        </p>
      </div>

      <div v-else class="grid grid-cols-2 gap-3">
        <button
          v-for="model in settingsStore.availableModels"
          :key="model"
          @click="switchModel(model)"
          class="p-3 rounded-lg border-2 text-left transition-all"
          :class="settingsStore.currentModel === model
            ? 'border-green-500 bg-slate-700'
            : 'border-slate-700 bg-slate-800 hover:border-slate-600'"
        >
          <div class="flex items-center justify-between">
            <span class="text-white font-medium">{{ model }}</span>
            <span v-if="settingsStore.currentModel === model" class="text-green-400">✓</span>
          </div>
        </button>
      </div>

      <p class="text-xs text-slate-500 mt-4">
        💡 点击模型即可热切换，无需重启服务
      </p>
    </div>
  </div>
</template>
