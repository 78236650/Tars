<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { rolesApi, type RoleTemplate } from '@/api'
import { useI18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import RoleEditor from '@/components/settings/RoleEditor.vue'

const { t } = useI18n()
const authStore = useAuthStore()

const templates = ref<RoleTemplate[]>([])
const loading = ref(false)
const showEditor = ref(false)
const editingTemplate = ref<RoleTemplate | null>(null)
const deletingId = ref<string | null>(null)

const isAdmin = computed(() => authStore.user?.role === 'admin')

const loadTemplates = async () => {
  loading.value = true
  try {
    templates.value = await rolesApi.list()
  } catch (e) {
    console.error('加载角色模板失败:', e)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingTemplate.value = null
  showEditor.value = true
}

const openEdit = (tmpl: RoleTemplate) => {
  editingTemplate.value = { ...tmpl }
  showEditor.value = true
}

const closeEditor = () => {
  showEditor.value = false
  editingTemplate.value = null
}

const handleSaved = () => {
  closeEditor()
  loadTemplates()
}

const confirmDelete = async (tmpl: RoleTemplate) => {
  if (tmpl.is_builtin) return
  if (!confirm(t('roles.deleteConfirm', { name: tmpl.name }))) return
  deletingId.value = tmpl.id
  try {
    await rolesApi.delete(tmpl.id)
    await loadTemplates()
  } catch (e) {
    console.error('删除失败:', e)
  } finally {
    deletingId.value = null
  }
}

// 工具列表（与后端保持一致）
const toolList = [
  'weather', 'web_search', 'web_fetch', 'file', 'file_write',
  'shell', 'command', 'python_exec', 'process', 'network',
  'memory', 'knowledge_search', 'cronjob', 'calculator',
  'bi_query', 'bi_generate_chart', 'meeting_recognizer',
]

const moduleList = ['bi', 'knowledge', 'meeting', 'skillhub']

const showTools = (tmpl: RoleTemplate): string => {
  if (tmpl.allowed_tools === '*') return t('roles.allTools')
  const arr = tmpl.allowed_tools as string[]
  if (arr.length === 0) return t('roles.noTools')
  return arr.slice(0, 4).join(', ') + (arr.length > 4 ? ` +${arr.length - 4}` : '')
}

const showModules = (tmpl: RoleTemplate): string => {
  if (tmpl.allowed_modules.length === 0) return t('roles.noModules')
  return tmpl.allowed_modules.slice(0, 3).join(', ') + (tmpl.allowed_modules.length > 3 ? ' ...' : '')
}

// 角色图标映射
const roleIcons: Record<string, string> = {
  admin: 'lucide:lock-keyhole',
  developer: 'lucide:laptop',
  analyst: 'lucide:bar-chart-3',
  operator: 'lucide:wrench',
  standard: 'lucide:user',
  readonly: 'lucide:eye',
}

const getRoleIcon = (id: string) => roleIcons[id] || 'lucide:file-pen-line'

onMounted(loadTemplates)
</script>

<template>
  <div class="mx-auto max-w-5xl">
    <div class="rounded-xl bg-slate-800 p-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="text-xl font-semibold text-white">{{ t('roles.title') }}</h2>
          <p class="text-sm text-slate-400 mt-1">{{ t('roles.subtitle') }}</p>
        </div>
        <button
          v-if="isAdmin"
          @click="openCreate"
          class="px-4 py-2 bg-amber-500 hover:bg-amber-400 rounded-lg text-stone-950 font-medium transition-colors"
        >
          + {{ t('roles.createTemplate') }}
        </button>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="text-center py-12">
        <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-amber-400 border-t-transparent"></div>
      </div>

      <!-- 模板网格 -->
      <div v-else-if="templates.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="tmpl in templates"
          :key="tmpl.id"
          class="rounded-xl border border-slate-700 bg-slate-800/60 p-5 transition hover:border-slate-600"
        >
          <!-- 头部 -->
          <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-2">
              <BaseIcon :icon="getRoleIcon(tmpl.id)" :size="24" />
              <div>
                <h3 class="text-sm font-semibold text-white">{{ tmpl.name }}</h3>
                <span
                  v-if="tmpl.is_builtin"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300"
                >{{ t('roles.builtin') }}</span>
              </div>
            </div>
            <div v-if="tmpl.user_count !== undefined" class="text-xs text-slate-400">
              {{ t('roles.userCount', { count: tmpl.user_count }) }}
            </div>
          </div>

          <!-- 描述 -->
          <p class="text-xs text-slate-400 mb-3 line-clamp-2">{{ tmpl.description }}</p>

          <!-- 权限摘要 -->
          <div class="space-y-1.5 mb-4">
            <div class="flex items-center gap-2 text-xs">
              <span class="text-slate-500 w-14 flex-shrink-0">{{ t('roles.tools') }}:</span>
              <span class="text-slate-300 truncate">{{ showTools(tmpl) }}</span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <span class="text-slate-500 w-14 flex-shrink-0">{{ t('roles.modules') }}:</span>
              <span class="text-slate-300 truncate">{{ showModules(tmpl) }}</span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <span class="text-slate-500 w-14 flex-shrink-0">{{ t('roles.concurrent') }}:</span>
              <span class="text-slate-300">{{ tmpl.max_concurrent }}</span>
            </div>
          </div>

          <!-- 操作 -->
          <div v-if="isAdmin && tmpl.id !== 'admin'" class="flex items-center gap-2 pt-3 border-t border-slate-700">
            <button
              @click="openEdit(tmpl)"
              class="text-xs text-amber-400 hover:text-amber-300 transition"
            >
              {{ t('common.edit') }}
            </button>
            <button
              v-if="!tmpl.is_builtin"
              @click="confirmDelete(tmpl)"
              :disabled="deletingId === tmpl.id"
              class="text-xs text-red-400 hover:text-red-300 transition disabled:opacity-50"
            >
              {{ deletingId === tmpl.id ? '...' : t('common.delete') }}
            </button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-12 text-slate-400">
        <BaseIcon icon="lucide:shield-check" :size="64" class="mx-auto mb-3" />
        <p>{{ t('roles.empty') }}</p>
      </div>
    </div>

    <!-- Editor Modal -->
    <RoleEditor
      v-if="showEditor"
      :template="editingTemplate"
      @close="closeEditor"
      @saved="handleSaved"
    />
  </div>
</template>
