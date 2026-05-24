<script setup lang="ts">
import { computed, ref } from 'vue'
import { rolesApi, type RoleTemplate } from '@/api'
import { useI18n } from '@/i18n'

const props = defineProps<{
  template: RoleTemplate | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const { t } = useI18n()
const saving = ref(false)
const error = ref('')

const isEdit = computed(() => props.template !== null)

// 所有可用工具
const allTools = [
  'weather', 'web_search', 'web_fetch', 'file', 'file_write',
  'shell', 'command', 'python_exec', 'process', 'network',
  'memory', 'knowledge_search', 'cronjob', 'calculator',
  'bi_query', 'bi_generate_chart', 'meeting_recognizer',
  'archival_insert', 'core_memory_append', 'core_memory_replace',
  'task_planner',
]

const allModules = ['bi', 'knowledge', 'meeting', 'skillhub', 'insight']

// 表单数据
const form = ref({
  id: props.template?.id || '',
  name: props.template?.name || '',
  description: props.template?.description || '',
  allowed_tools: (props.template?.allowed_tools === '*'
    ? [...allTools]
    : [...(props.template?.allowed_tools as string[] || [])]) as string[],
  allowed_modules: [...(props.template?.allowed_modules || [])] as string[],
  max_concurrent: props.template?.max_concurrent || 1,
  workspace_restriction: props.template?.workspace_restriction ?? true,
})

const nameError = computed(() => {
  if (!form.value.name.trim()) return t('roles.nameRequired')
  return ''
})

const toggleTool = (tool: string) => {
  const idx = form.value.allowed_tools.indexOf(tool)
  if (idx >= 0) {
    form.value.allowed_tools.splice(idx, 1)
  } else {
    form.value.allowed_tools.push(tool)
  }
}

const toggleModule = (mod: string) => {
  const idx = form.value.allowed_modules.indexOf(mod)
  if (idx >= 0) {
    form.value.allowed_modules.splice(idx, 1)
  } else {
    form.value.allowed_modules.push(mod)
  }
}

const toggleAllTools = () => {
  if (form.value.allowed_tools.length === allTools.length) {
    form.value.allowed_tools = []
  } else {
    form.value.allowed_tools = [...allTools]
  }
}

const handleSave = async () => {
  if (!form.value.name.trim()) return
  saving.value = true
  error.value = ''
  try {
    if (isEdit.value) {
      await rolesApi.update(props.template!.id, {
        name: form.value.name.trim(),
        description: form.value.description.trim(),
        allowed_tools: form.value.allowed_tools,
        allowed_modules: form.value.allowed_modules,
        max_concurrent: form.value.max_concurrent,
        workspace_restriction: form.value.workspace_restriction,
      })
    } else {
      await rolesApi.create({
        id: form.value.id.trim() || form.value.name.trim().toLowerCase().replace(/\s+/g, '_'),
        name: form.value.name.trim(),
        description: form.value.description.trim(),
        allowed_tools: form.value.allowed_tools,
        denied_tools: [],
        allowed_modules: form.value.allowed_modules,
        max_concurrent: form.value.max_concurrent,
        workspace_restriction: form.value.workspace_restriction,
      })
    }
    emit('saved')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || t('common.error')
  } finally {
    saving.value = false
  }
}

// 工具中文名映射
const toolLabels: Record<string, string> = {
  weather: '🌤 天气', web_search: '🔍 网页搜索', web_fetch: '📥 网页抓取',
  file: '📄 文件读取', file_write: '✏️ 文件写入', shell: '💻 Shell',
  command: '⌨️ 命令', python_exec: '🐍 Python', process: '🔌 进程',
  network: '🌐 网络', memory: '🧠 记忆', knowledge_search: '📚 知识搜索',
  cronjob: '⏰ 定时任务', calculator: '🔢 计算器',
  bi_query: '📊 BI查询', bi_generate_chart: '📈 BI图表', meeting_recognizer: '🎙 会议识别',
  archival_insert: '💾 归档插入', core_memory_append: '➕ 核心记忆追加', core_memory_replace: '🔄 核心记忆替换',
  task_planner: '📋 任务规划',
}

const moduleLabels: Record<string, string> = {
  bi: '📊 BI 工作台',
  knowledge: '📚 知识库',
  meeting: '🎙 会议助手',
  skillhub: '🧩 SkillHub',
}
</script>

<template>
  <div class="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4" @click.self="emit('close')">
    <div class="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-800 shadow-[0_30px_100px_rgba(0,0,0,0.6)] max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <h3 class="text-lg font-semibold text-white">
          {{ isEdit ? t('roles.editTemplate') : t('roles.createTemplate') }}
        </h3>
        <button @click="emit('close')" class="text-slate-400 hover:text-white transition">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Body -->
      <div class="px-6 py-4 overflow-y-auto flex-1 space-y-5">
        <!-- 错误提示 -->
        <div v-if="error" class="text-sm text-red-400 bg-red-900/20 rounded-lg px-3 py-2">{{ error }}</div>

        <!-- 基本字段 -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">
              {{ t('roles.templateName') }} <span class="text-red-400">*</span>
            </label>
            <input
              v-model="form.name"
              :disabled="isEdit && (props.template?.is_builtin ?? false)"
              class="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-amber-400/50 focus:outline-none disabled:opacity-50"
              :placeholder="t('roles.templateNamePh')"
            />
            <p v-if="nameError" class="text-xs text-red-400 mt-1">{{ nameError }}</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('roles.templateId') }}</label>
            <input
              v-model="form.id"
              :disabled="isEdit"
              class="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-amber-400/50 focus:outline-none disabled:opacity-50 font-mono"
              :placeholder="t('roles.templateIdPh')"
            />
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('roles.templateDesc') }}</label>
          <textarea
            v-model="form.description"
            rows="2"
            class="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-amber-400/50 focus:outline-none resize-none"
            :placeholder="t('roles.templateDescPh')"
          />
        </div>

        <!-- 工具权限 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-medium text-slate-400">{{ t('roles.toolPermissions') }}</label>
            <button
              @click="toggleAllTools"
              class="text-xs text-amber-400 hover:text-amber-300 transition"
            >
              {{ form.allowed_tools.length === allTools.length ? t('roles.deselectAll') : t('roles.selectAll') }}
            </button>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5">
            <button
              v-for="tool in allTools"
              :key="tool"
              @click="toggleTool(tool)"
              class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-left transition border"
              :class="form.allowed_tools.includes(tool)
                ? 'bg-amber-500/15 border-amber-500/30 text-amber-200'
                : 'border-slate-700 bg-slate-700/50 text-slate-400 hover:border-slate-600'"
            >
              <span class="text-[10px]">{{ form.allowed_tools.includes(tool) ? '☑' : '☐' }}</span>
              <span class="truncate">{{ toolLabels[tool] || tool }}</span>
            </button>
          </div>
        </div>

        <!-- 模块访问 -->
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-2">{{ t('roles.moduleAccess') }}</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="mod in allModules"
              :key="mod"
              @click="toggleModule(mod)"
              class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs transition border"
              :class="form.allowed_modules.includes(mod)
                ? 'bg-amber-500/15 border-amber-500/30 text-amber-200'
                : 'border-slate-700 bg-slate-700/50 text-slate-400 hover:border-slate-600'"
            >
              <span class="text-[10px]">{{ form.allowed_modules.includes(mod) ? '☑' : '☐' }}</span>
              <span>{{ moduleLabels[mod] || mod }}</span>
            </button>
          </div>
        </div>

        <!-- 资源限制 -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('roles.maxConcurrent') }}</label>
            <select
              v-model.number="form.max_concurrent"
              class="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-amber-400/50 focus:outline-none"
            >
              <option :value="1">1</option>
              <option :value="2">2</option>
              <option :value="3">3</option>
              <option :value="5">5</option>
              <option :value="10">10</option>
            </select>
          </div>
          <div class="flex items-end pb-0.5">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                v-model="form.workspace_restriction"
                class="w-4 h-4 rounded accent-amber-500"
              />
              <span class="text-xs text-slate-400">{{ t('roles.workspaceRestrict') }}</span>
            </label>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex justify-end gap-3 px-6 py-4 border-t border-slate-700">
        <button
          @click="emit('close')"
          class="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:text-white hover:border-slate-500 text-sm transition"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          @click="handleSave"
          :disabled="saving || !form.name.trim()"
          class="px-6 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-950 font-medium text-sm transition disabled:opacity-50"
        >
          {{ saving ? t('common.loading') : (isEdit ? t('common.save') : t('common.create')) }}
        </button>
      </div>
    </div>
  </div>
</template>
