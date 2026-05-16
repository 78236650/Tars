<template>
  <div class="meeting-settings">
    <button class="settings-toggle" @click="showPanel = !showPanel">
      ⚙️ 设置
    </button>

    <div v-if="showPanel" class="settings-panel">
      <!-- 模型选择 -->
      <div class="setting-section">
        <h4>摘要模型</h4>
        <div class="model-selector">
          <select v-model="selectedModel" @change="switchModel">
            <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
          </select>
          <span class="model-hint">独立于主 Agent，不影响聊天模型</span>
        </div>
      </div>

      <!-- 提示词模板 -->
      <div class="setting-section">
        <h4>摘要模板</h4>
        <div class="template-list">
          <label
            v-for="tpl in templates"
            :key="tpl.id"
            class="template-option"
            :class="{ active: activeTemplate === tpl.id }"
          >
            <input type="radio" :value="tpl.id" v-model="activeTemplate" @change="selectTemplate(tpl.id)" />
            <div>
              <span class="tpl-name">{{ tpl.name }}</span>
              <span v-if="tpl.is_default" class="default-badge">默认</span>
              <p class="tpl-desc">{{ tpl.description }}</p>
            </div>
          </label>
          <label class="template-option" :class="{ active: activeTemplate === 'custom' }">
            <input type="radio" value="custom" v-model="activeTemplate" @change="selectTemplate('custom')" />
            <div>
              <span class="tpl-name">自定义</span>
              <p class="tpl-desc">使用自定义提示词</p>
            </div>
          </label>
        </div>
      </div>

      <!-- 自定义提示词编辑 -->
      <div v-if="activeTemplate === 'custom'" class="setting-section">
        <h4>自定义提示词</h4>
        <textarea
          v-model="customPrompt"
          class="prompt-editor"
          rows="8"
          placeholder="输入自定义摘要提示词..."
        ></textarea>
        <div class="prompt-actions">
          <button class="btn-save" @click="saveCustomPrompt">保存</button>
          <button class="btn-reset" @click="resetPrompt">恢复默认</button>
        </div>
      </div>

      <!-- 预览当前模板 -->
      <div v-if="activeTemplate !== 'custom' && currentPromptPreview" class="setting-section">
        <h4>模板预览</h4>
        <pre class="prompt-preview">{{ currentPromptPreview }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

const showPanel = ref(false)
const templates = ref<any[]>([])
const activeTemplate = ref('general')
const customPrompt = ref('')
const availableModels = ref<string[]>([])
const selectedModel = ref('')

const currentPromptPreview = computed(() => {
  const tpl = templates.value.find(t => t.id === activeTemplate.value)
  return tpl?.prompt || ''
})

onMounted(async () => {
  await loadTemplates()
  await loadModels()
  await loadCurrentModel()
})

async function loadTemplates() {
  try {
    const { data } = await api.get('/meeting/settings/templates')
    templates.value = data.templates
    activeTemplate.value = data.active_template
    if (data.custom_prompt) customPrompt.value = data.custom_prompt
  } catch {}
}

async function loadModels() {
  try {
    const { data } = await api.get('/models/')
    availableModels.value = data.ollama_models || []
  } catch {}
}

async function loadCurrentModel() {
  try {
    const { data } = await api.get('/meeting/settings/model')
    selectedModel.value = data.model
  } catch {}
}

async function switchModel() {
  try {
    await api.put('/meeting/settings/model', { provider: 'ollama', model: selectedModel.value })
  } catch (e: any) {
    alert(e.response?.data?.detail || '模型切换失败')
  }
}

async function selectTemplate(id: string) {
  if (id !== 'custom') {
    customPrompt.value = ''
    try { await api.delete('/meeting/settings/prompt') } catch {}
  }
}

async function saveCustomPrompt() {
  try {
    await api.put('/meeting/settings/prompt', { prompt: customPrompt.value })
    activeTemplate.value = 'custom'
  } catch (e: any) {
    alert('保存失败')
  }
}

async function resetPrompt() {
  try {
    const { data } = await api.delete('/meeting/settings/prompt')
    activeTemplate.value = data.active_template || 'general'
    customPrompt.value = ''
  } catch {}
}
</script>

<style scoped>
.meeting-settings { position: relative; margin-bottom: 12px; }
.settings-toggle {
  padding: 6px 12px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px;
  background: rgba(255,255,255,0.04); cursor: pointer; font-size: 13px; color: #d6d3d1;
}
.settings-toggle:hover { background: rgba(255,255,255,0.08); }

.settings-panel {
  margin-top: 8px; padding: 16px;
  background: rgba(20,17,15,0.92);
  border: 1px solid rgba(245, 158, 11, 0.12); border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}

.setting-section { margin-bottom: 16px; }
.setting-section h4 { margin: 0 0 8px; font-size: 13px; color: #d6d3d1; font-weight: 600; }

.model-selector select {
  padding: 6px 10px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px;
  font-size: 13px; min-width: 180px; background: rgba(255,255,255,0.04); color: #e7e5e4;
}
.model-hint { font-size: 11px; color: #78716c; margin-left: 8px; }

.template-list { display: flex; flex-direction: column; gap: 6px; }
.template-option {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 10px; border: 1px solid rgba(245, 158, 11, 0.12); border-radius: 6px;
  cursor: pointer; transition: all 0.15s; background: rgba(255,255,255,0.02);
}
.template-option:hover { border-color: rgba(245, 158, 11, 0.3); }
.template-option.active { border-color: #d97706; background: rgba(217, 119, 6, 0.08); }
.template-option input { margin-top: 2px; }
.tpl-name { font-size: 13px; font-weight: 500; color: #d6d3d1; }
.tpl-desc { margin: 2px 0 0; font-size: 11px; color: #78716c; }
.default-badge { font-size: 10px; background: rgba(217, 119, 6, 0.15); color: #fbbf24; padding: 1px 5px; border-radius: 3px; margin-left: 6px; }

.prompt-editor {
  width: 100%; padding: 10px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px;
  font-size: 12px; font-family: monospace; resize: vertical; line-height: 1.5;
  background: rgba(255,255,255,0.04); color: #e7e5e4;
}
.prompt-actions { margin-top: 8px; display: flex; gap: 8px; }
.btn-save { padding: 5px 12px; background: #d97706; color: #0c0b09; border: none; border-radius: 5px; font-size: 12px; font-weight: 500; cursor: pointer; }
.btn-save:hover { background: #f59e0b; }
.btn-reset { padding: 5px 12px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 5px; font-size: 12px; color: #d6d3d1; cursor: pointer; }

.prompt-preview {
  padding: 10px; background: rgba(255,255,255,0.03); border: 1px solid rgba(245, 158, 11, 0.1); border-radius: 6px;
  font-size: 11px; white-space: pre-wrap; max-height: 150px; overflow-y: auto;
  color: #a8a29e; line-height: 1.5;
}
</style>
