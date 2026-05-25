<template>
  <div class="meeting-settings">
    <button class="settings-toggle" @click="showPanel = !showPanel">⚙️ {{ t('meeting.settingsToggle') }}</button>

    <div v-if="showPanel" class="settings-panel">
      <!-- 语音识别 -->
      <div class="setting-section">
        <h4>{{ t('meeting.asrSection') }}</h4>
        <div class="asr-form">
          <label class="field-label">{{ t('meeting.asrLanguage') }}</label>
          <select v-model="selectedAsrLanguage" @change="onAsrLanguageChange">
            <option v-for="opt in asrLanguageOptions" :key="opt.id" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>

          <label class="field-label">{{ t('meeting.whisperModel') }}</label>
          <select v-model="selectedWhisperModel" @change="onWhisperModelChange">
            <option v-for="opt in whisperModelOptions" :key="opt.id" :value="opt.id">
              {{ opt.id }} — {{ opt.label }}
            </option>
          </select>

          <span class="model-hint block-hint">
            {{ t('meeting.asrModelHint', { backend: asrBackend, model: asrDisplayModel }) }}
          </span>
        </div>
      </div>

      <!-- 摘要模型 -->
      <div class="setting-section">
        <h4>{{ t('meeting.summaryModel') }}</h4>
        <div class="summary-model-form">
          <label class="field-label">{{ t('meeting.summaryProvider') }}</label>
          <select v-model="summaryProvider" @change="onSummaryProviderChange">
            <option value="ollama">Ollama</option>
            <option value="openai_compatible">{{ t('meeting.summaryRemote') }}</option>
          </select>

          <template v-if="summaryProvider === 'openai_compatible'">
            <label class="field-label">{{ t('meeting.summaryEndpoint') }}</label>
            <select v-model="summaryEndpointId" @change="onSummaryEndpointChange">
              <option :value="null">{{ t('meeting.summaryPickEndpoint') }}</option>
              <option v-for="ep in endpoints" :key="ep.id" :value="ep.id">{{ ep.name }}</option>
            </select>
          </template>

          <label class="field-label">{{ t('meeting.summaryPickModel') }}</label>
          <select v-model="selectedModel" @change="switchModel">
            <option value="">{{ t('meeting.summaryPickModel') }}</option>
            <option v-for="m in summaryModelChoices" :key="m" :value="m">{{ m }}</option>
          </select>
          <span class="model-hint">{{ t('meeting.modelHint') }}</span>
        </div>
      </div>

      <!-- 提示词模板 -->
      <div class="setting-section">
        <h4>{{ t('meeting.summaryTemplate') }}</h4>
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
              <span v-if="tpl.is_default" class="default-badge">{{ t('meeting.templateDefault') }}</span>
              <p class="tpl-desc">{{ tpl.description }}</p>
            </div>
          </label>
          <label class="template-option" :class="{ active: activeTemplate === 'custom' }">
            <input type="radio" value="custom" v-model="activeTemplate" @change="selectTemplate('custom')" />
            <div>
              <span class="tpl-name">{{ t('meeting.templateCustomName') }}</span>
              <p class="tpl-desc">{{ t('meeting.templateCustomDesc') }}</p>
            </div>
          </label>
        </div>
      </div>

      <!-- 自定义提示词编辑 -->
      <div v-if="activeTemplate === 'custom'" class="setting-section">
        <h4>{{ t('meeting.customPrompt') }}</h4>
        <textarea
          v-model="customPrompt"
          class="prompt-editor"
          rows="8"
          :placeholder="t('meeting.customPromptPlaceholder')"
        ></textarea>
        <div class="prompt-actions">
          <button class="btn-save" @click="saveCustomPrompt">{{ t('common.save') }}</button>
          <button class="btn-reset" @click="resetPrompt">{{ t('common.reset') }}</button>
        </div>
      </div>

      <!-- 预览当前模板 -->
      <div v-if="activeTemplate !== 'custom' && currentPromptPreview" class="setting-section">
        <h4>{{ t('meeting.templatePreview') }}</h4>
        <pre class="prompt-preview">{{ currentPromptPreview }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { meetingApi, modelApi } from '@/api'
import type { Endpoint } from '@/types'
import { getMeetingAsrLanguage, setMeetingAsrLanguage, type MeetingAsrLanguage } from '@/composables/useMeetingAsrLanguage'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'

const showPanel = ref(false)
const templates = ref<any[]>([])
const activeTemplate = ref('general')
const customPrompt = ref('')
const availableModels = ref<string[]>([])
const endpoints = ref<Endpoint[]>([])
const summaryProvider = ref<'ollama' | 'openai_compatible'>('ollama')
const summaryEndpointId = ref<string | null>(null)
const selectedModel = ref('')
const asrDisplayModel = ref('whisper-small')
const asrBackend = ref('whisper')
const selectedWhisperModel = ref('small')
const whisperModelOptions = ref<Array<{ id: string; label: string }>>([])
const asrLanguageOptions = ref<Array<{ id: string; label: string }>>([])
const selectedAsrLanguage = ref<MeetingAsrLanguage>(getMeetingAsrLanguage())
const { t } = useI18n()
const toast = useToast()

const currentPromptPreview = computed(() => {
  const tpl = templates.value.find(t => t.id === activeTemplate.value)
  return tpl?.prompt || ''
})

const summaryModelChoices = computed(() => {
  if (summaryProvider.value === 'ollama') return availableModels.value
  const ep = endpoints.value.find((e) => e.id === summaryEndpointId.value)
  return ep?.models || []
})

onMounted(async () => {
  selectedAsrLanguage.value = getMeetingAsrLanguage()
  await Promise.all([loadTemplates(), loadModels()])
  await loadCurrentModel()
  await loadAsrSettings()
})

async function loadAsrSettings() {
  try {
    const data = await meetingApi.getAsrSettings()
    asrDisplayModel.value = data.model
    asrBackend.value = data.backend
    selectedWhisperModel.value = data.whisper_model || 'small'
    whisperModelOptions.value = data.whisper_model_options || []
    asrLanguageOptions.value = data.language_options
    if (!asrLanguageOptions.value.some((o) => o.id === selectedAsrLanguage.value)) {
      selectedAsrLanguage.value = (data.language_default as MeetingAsrLanguage) || 'zh'
      setMeetingAsrLanguage(selectedAsrLanguage.value)
    }
  } catch {}
}

async function onWhisperModelChange() {
  if (!selectedWhisperModel.value) return
  try {
    const data = await meetingApi.setAsrSettings({ whisper_model: selectedWhisperModel.value })
    asrDisplayModel.value = data.model || `whisper-${selectedWhisperModel.value}`
    toast.success(t('meeting.whisperModelSwitchSuccess'))
  } catch (e: unknown) {
    toast.error(getErrorDetail(e, t('meeting.whisperModelSwitchFailed')))
    await loadAsrSettings()
  }
}

function onAsrLanguageChange() {
  setMeetingAsrLanguage(selectedAsrLanguage.value)
}

async function loadTemplates() {
  try {
    const data = await meetingApi.getPromptTemplates()
    templates.value = data.templates
    activeTemplate.value = data.active_template
    if (data.custom_prompt) customPrompt.value = data.custom_prompt
  } catch {}
}

async function loadModels() {
  try {
    const data = await modelApi.getModelsOverview()
    availableModels.value = data.ollama_models || []
    endpoints.value = data.endpoints || []
  } catch {}
}

function onSummaryProviderChange() {
  selectedModel.value = ''
  if (summaryProvider.value === 'openai_compatible' && !summaryEndpointId.value) {
    summaryEndpointId.value = endpoints.value[0]?.id || null
  }
}

function onSummaryEndpointChange() {
  selectedModel.value = ''
}

async function loadCurrentModel() {
  try {
    const data = await meetingApi.getModelSettings()
    summaryProvider.value = (data.provider as 'ollama' | 'openai_compatible') || 'ollama'
    summaryEndpointId.value = data.endpoint_id ?? null
    selectedModel.value = data.model || ''
    if (summaryProvider.value === 'openai_compatible' && !summaryEndpointId.value) {
      summaryEndpointId.value = endpoints.value[0]?.id || null
    }
  } catch {}
}

async function switchModel() {
  if (!selectedModel.value) return
  try {
    await meetingApi.setModelSettings({
      provider: summaryProvider.value,
      model: selectedModel.value,
      endpoint_id: summaryProvider.value === 'openai_compatible' ? summaryEndpointId.value ?? undefined : undefined,
    })
    toast.success(t('meeting.modelSwitchSuccess'))
  } catch (e: any) {
    toast.error(getErrorDetail(e, t('meeting.modelSwitchFailed')))
  }
}

async function selectTemplate(id: string) {
  if (id !== 'custom') {
    customPrompt.value = ''
    try { await meetingApi.resetCustomPrompt() } catch {}
  }
}

async function saveCustomPrompt() {
  try {
    await meetingApi.saveCustomPrompt(customPrompt.value)
    activeTemplate.value = 'custom'
  } catch (e: any) {
    toast.error(t('meeting.saveFailed'))
  }
}

async function resetPrompt() {
  try {
    const data = await meetingApi.resetCustomPrompt()
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
.asr-form { display: flex; flex-direction: column; gap: 6px; }
.asr-form select {
  padding: 6px 10px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px;
  font-size: 13px; min-width: 180px; background: rgba(255,255,255,0.04); color: #e7e5e4;
}
.block-hint { margin-left: 0; margin-top: 4px; display: block; }
.summary-model-form { display: flex; flex-direction: column; gap: 6px; }
.summary-model-form select {
  padding: 6px 10px; border: 1px solid rgba(245, 158, 11, 0.15); border-radius: 6px;
  font-size: 13px; min-width: 180px; background: rgba(255,255,255,0.04); color: #e7e5e4;
}
.field-label { font-size: 11px; color: #78716c; margin-top: 4px; }
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
