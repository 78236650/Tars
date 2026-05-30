<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import ToolCard from '@/components/tools/ToolCard.vue'
import ToolDetailModal from '@/components/tools/ToolDetailModal.vue'
import AddToolModal from '@/components/tools/AddToolModal.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import TrySkillButton from '@/components/tools/TrySkillButton.vue'
import SkillInstallWizard, { type InstallWizardState } from '@/components/tools/SkillInstallWizard.vue'
import PendingArchivePanel from '@/components/tools/PendingArchivePanel.vue'
import { toolsApi, skillsApi, skillhubApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import type { Tool, SkillItem, SkillHubPackage } from '@/types'

const activeTab = ref<'builtin' | 'skills' | 'skillhub'>('builtin')
const loading = ref(false)
const searchQuery = ref('')
const { t } = useI18n()
const authStore = useAuthStore()

const builtinDescriptionKeys: Record<string, string> = {
  archival_insert: 'tools.builtinDescriptions.archival_insert',
  bi_generate_chart: 'tools.builtinDescriptions.bi_generate_chart',
  bi_list_datasources: 'tools.builtinDescriptions.bi_list_datasources',
  bi_query: 'tools.builtinDescriptions.bi_query',
  bi_schema_explore: 'tools.builtinDescriptions.bi_schema_explore',
  calculator: 'tools.builtinDescriptions.calculator',
  command: 'tools.builtinDescriptions.command',
  cronjob: 'tools.builtinDescriptions.cronjob',
  core_memory_append: 'tools.builtinDescriptions.core_memory_append',
  core_memory_replace: 'tools.builtinDescriptions.core_memory_replace',
  file: 'tools.builtinDescriptions.file',
  file_list: 'tools.builtinDescriptions.file_list',
  file_write: 'tools.builtinDescriptions.file_write',
  knowledge_search: 'tools.builtinDescriptions.knowledge_search',
  meeting_recognizer: 'tools.builtinDescriptions.meeting_recognizer',
  memory: 'tools.builtinDescriptions.memory',
  network: 'tools.builtinDescriptions.network',
  process: 'tools.builtinDescriptions.process',
  python_exec: 'tools.builtinDescriptions.python_exec',
  shell: 'tools.builtinDescriptions.shell',
  task_planner: 'tools.builtinDescriptions.task_planner',
  weather: 'tools.builtinDescriptions.weather',
  web_fetch: 'tools.builtinDescriptions.web_fetch',
  web_search: 'tools.builtinDescriptions.web_search',
}

const normalizeToolName = (value?: string) => value?.trim().toLowerCase() || ''

const localizeBuiltinTool = <T extends Tool>(tool: T): T => {
  if (tool.type !== 'builtin') {
    return tool
  }

  const normalizedName = normalizeToolName(tool.name) || normalizeToolName(tool.id)
  const descriptionKey = builtinDescriptionKeys[normalizedName]
  if (!descriptionKey) {
    return tool
  }

  const localizedDescription = t(descriptionKey)
  if (localizedDescription === descriptionKey) {
    return tool
  }

  return {
    ...tool,
    description: localizedDescription,
  }
}

// 内置工具
const tools = ref<Tool[]>([])
// 已安装技能
const skills = ref<SkillItem[]>([])
// v4.0.0: 技能统计
interface SkillStats {
  skill_id: string
  total_calls: number
  last_used: string | null
  first_used: string | null
}
const skillStats = ref<Record<string, SkillStats>>({})
// v4.0.0: 归档/激活中状态
const togglingSkillId = ref<string | null>(null)
// SkillHub
const hubResults = ref<SkillHubPackage[]>([])
const hubSearchQuery = ref('')
const hubSearching = ref(false)
const hubLoaded = ref(false)
const installingId = ref<string | null>(null)
const installMessage = ref<{ id: string; success: boolean; message: string; examplePrompt?: string } | null>(null)
const installWizardOpen = ref(false)
const installWizardState = ref<InstallWizardState | null>(null)
const hubFilter = ref<'all' | 'plugin' | 'prompt' | 'featured'>('all')
const installScope = ref<'tenant' | 'global'>('tenant')

// 弹窗
const showAddModal = ref(false)

// ========= 数据加载 =========

const loadTools = async () => {
  loading.value = true
  try {
    const resp = await toolsApi.listTools()
    tools.value = resp.data.tools || []
  } catch (e) {
    console.error('加载工具失败:', e)
  } finally {
    loading.value = false
  }
}

const loadSkills = async () => {
  try {
    const resp = await skillsApi.listSkills()
    skills.value = resp.data.skills || []
  } catch (e) {
    console.error('加载技能失败:', e)
  }
}

// v4.0.0: 加载技能调用统计
const loadSkillStats = async () => {
  try {
    const resp = await skillsApi.getStats()
    const items: any[] = resp.data?.items || resp.data || []
    const map: Record<string, SkillStats> = {}
    for (const item of items) {
      map[item.skill_id] = item
    }
    skillStats.value = map
  } catch (e) {
    console.error('加载技能统计失败:', e)
  }
}

// v4.0.0: 归档/激活切换
const toggleArchive = async (skillId: string, currentlyArchived: boolean) => {
  togglingSkillId.value = skillId
  try {
    if (currentlyArchived) {
      await skillsApi.activate(skillId)
    } else {
      await skillsApi.archive(skillId)
    }
    await loadSkills()
  } catch (e) {
    console.error('操作失败:', e)
  } finally {
    togglingSkillId.value = null
  }
}

const loadCatalog = async () => {
  hubSearching.value = true
  try {
    const resp = await skillhubApi.getCatalog()
    hubResults.value = resp.data.results || []
    hubLoaded.value = true
  } catch (e) {
    console.error('加载目录失败:', e)
    hubResults.value = []
  } finally {
    hubSearching.value = false
  }
}

const searchHub = async () => {
  hubSearching.value = true
  try {
    const resp = await skillhubApi.search(hubSearchQuery.value)
    hubResults.value = resp.data.results || []
  } catch (e) {
    console.error('搜索失败:', e)
  } finally {
    hubSearching.value = false
  }
}

const pkgNameFor = (skillId: string) => {
  const pkg = hubResults.value.find(p => p.id === skillId)
  return pkg?.name || skillId.split('/').pop() || skillId
}

const installFromHub = async (
  skillId: string,
  options?: { confirmPermissions?: boolean; skipDependencyCheck?: boolean; scope?: 'tenant' | 'global' },
) => {
  installingId.value = skillId
  installMessage.value = null
  const scope = options?.scope ?? installScope.value
  try {
    const resp = await skillhubApi.install(skillId, { ...options, scope })
    const data = resp.data
    if (data.needs_confirmation) {
      installWizardState.value = {
        skillId,
        skillName: pkgNameFor(skillId),
        success: false,
        needsConfirmation: true,
        permissions: data.permissions || [],
      }
      installWizardOpen.value = true
      return
    }
    if (data.needs_setup) {
      installWizardState.value = {
        skillId,
        skillName: pkgNameFor(skillId),
        success: false,
        needsSetup: true,
        installHints: data.install_hints || [],
      }
      installWizardOpen.value = true
      return
    }
    installWizardState.value = {
      skillId,
      skillName: pkgNameFor(skillId),
      success: true,
      usage: data.usage || t('tools.installSuccess'),
      examplePrompt: data.example_prompt || '',
    }
    installWizardOpen.value = true
    installMessage.value = {
      id: skillId,
      success: true,
      message: data.usage || t('tools.installSuccess'),
      examplePrompt: data.example_prompt || '',
    }
    await loadSkills()
    await refreshCatalogStatus()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    const message = typeof detail === 'string' ? detail : (detail?.error || t('tools.installFailed'))
    installWizardState.value = {
      skillId,
      skillName: pkgNameFor(skillId),
      success: false,
      errorMessage: message,
    }
    installWizardOpen.value = true
    installMessage.value = {
      id: skillId,
      success: false,
      message,
    }
  } finally {
    installingId.value = null
  }
}

const closeInstallWizard = () => {
  installWizardOpen.value = false
  installWizardState.value = null
}

const confirmWizardPermissions = () => {
  const skillId = installWizardState.value?.skillId
  if (!skillId) return
  installFromHub(skillId, { confirmPermissions: true })
}

const skipSetupAndInstall = () => {
  const skillId = installWizardState.value?.skillId
  if (!skillId) return
  installFromHub(skillId, { skipDependencyCheck: true })
}

const sourceLabel = (source?: string) => {
  if (source === 'bundled') return t('tools.sourceBundled')
  if (source === 'skills_sh') return t('tools.sourceSkillsSh')
  if (source === 'github') return t('tools.sourceGithub')
  if (source === 'package') return t('tools.sourcePackage')
  return source || ''
}

const refreshCatalogStatus = async () => {
  try {
    const resp = await skillhubApi.getCatalog()
    hubResults.value = resp.data.results || []
  } catch (e) {
    // ignore
  }
}

// ========= 过滤 =========

const localizedTools = computed(() => tools.value.map(localizeBuiltinTool))

const selectedToolRaw = ref<Tool | SkillItem | null>(null)

const selectedTool = computed(() => {
  if (!selectedToolRaw.value) {
    return null
  }
  return selectedToolRaw.value.type === 'builtin'
    ? localizeBuiltinTool(selectedToolRaw.value as Tool)
    : selectedToolRaw.value
})

const filteredTools = computed(() => {
  if (!searchQuery.value) return localizedTools.value
  const q = searchQuery.value.toLowerCase()
  return localizedTools.value.filter(item => item.name.toLowerCase().includes(q) || item.description.toLowerCase().includes(q))
})

const filteredSkills = computed(() => {
  if (!searchQuery.value) return skills.value
  const q = searchQuery.value.toLowerCase()
  return skills.value.filter(s => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q))
})

const filteredHubResults = computed(() => {
  let results = hubResults.value
  if (hubFilter.value === 'featured') {
    results = results.filter(pkg => pkg.featured)
  } else if (hubFilter.value !== 'all') {
    results = results.filter(pkg => pkg.type === hubFilter.value)
  }
  return [...results].sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)))
})

// ========= 操作 =========

const handleToolClick = (tool: Tool | SkillItem) => {
  selectedToolRaw.value = tool
}

const handleCloseDetail = () => {
  selectedToolRaw.value = null
  loadTools()
  loadSkills()
}

// SkillHub Tab 激活时自动加载目录
const onTabChange = (tab: 'builtin' | 'skills' | 'skillhub') => {
  activeTab.value = tab
  if (tab === 'skills') {
    loadSkillStats()
  }
  if (tab === 'skillhub' && !hubLoaded.value) {
    loadCatalog()
  }
}

onMounted(() => {
  loadTools()
  loadSkills()
  loadSkillStats()
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
      <header class="flex items-center justify-between border-b border-amber-100/10 px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 via-orange-500 to-amber-700 shadow-[0_10px_30px_rgba(217,119,6,0.35)]">
            <span class="text-lg font-bold text-stone-950">T</span>
          </div>
          <div>
            <h1 class="text-lg font-semibold text-stone-100">{{ t('tools.title') }}</h1>
            <p class="text-sm text-stone-400">{{ t('tools.subtitle') }}</p>
          </div>
        </div>
        <button
          @click="showAddModal = true"
          class="flex items-center gap-2 rounded-2xl bg-amber-500 px-4 py-2 font-medium text-stone-950 transition hover:bg-amber-400"
        >
          <BaseIcon icon="lucide:plus" :size="16" />
          <span>{{ t('tools.addSkill') }}</span>
        </button>
      </header>

      <!-- Tab 栏 -->
      <div class="flex border-b border-amber-100/10 px-6">
        <button
          @click="onTabChange('builtin')"
          class="px-5 py-3 text-sm font-medium transition"
          :class="activeTab === 'builtin' ? 'border-b-2 border-amber-400 text-amber-200' : 'text-stone-400 hover:text-stone-100'"
        >{{ t('tools.tabBuiltin') }}</button>
        <button
          @click="onTabChange('skills')"
          class="px-5 py-3 text-sm font-medium transition"
          :class="activeTab === 'skills' ? 'border-b-2 border-amber-400 text-amber-200' : 'text-stone-400 hover:text-stone-100'"
        >{{ t('tools.tabSkills') }} ({{ skills.length }})</button>
        <button
          @click="onTabChange('skillhub')"
          class="px-5 py-3 text-sm font-medium transition"
          :class="activeTab === 'skillhub' ? 'border-b-2 border-amber-400 text-amber-200' : 'text-stone-400 hover:text-stone-100'"
        >{{ t('tools.tabSkillhub') }}</button>
      </div>

      <div class="flex-1 overflow-y-auto p-6">
        <div class="mx-auto max-w-6xl">

          <!-- 搜索栏（内置工具 + 已安装技能 Tab） -->
          <div v-if="activeTab !== 'skillhub'" class="mb-6">
            <div class="relative">
              <BaseIcon icon="lucide:search" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-stone-500" />
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="t('tools.searchPlaceholder')"
                class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] py-2 pl-10 pr-4 text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
              />
            </div>
          </div>

          <!-- Tab 1: 内置工具 -->
          <div v-if="activeTab === 'builtin'">
            <div v-if="loading" class="text-center py-12">
              <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-amber-400 border-t-transparent"></div>
            </div>
            <div v-else-if="filteredTools.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <ToolCard v-for="tool in filteredTools" :key="tool.id" :tool="tool" @click="handleToolClick(tool)" />
            </div>
            <div v-else class="py-12 text-center text-stone-400">{{ t('tools.noTools') }}</div>
          </div>

          <!-- Tab 2: 已安装技能 (v4.0.0: 统计 + 归档) -->
          <div v-if="activeTab === 'skills'">
            <PendingArchivePanel />
            <div v-if="filteredSkills.length > 0">
              <!-- 表头（桌面端） -->
              <div class="hidden lg:grid grid-cols-12 gap-4 px-4 py-2 mb-2 text-xs font-medium text-stone-400 uppercase tracking-[0.05em]">
                <span class="col-span-3">{{ t('tools.skillName') }}</span>
                <span class="col-span-4">{{ t('tools.skillDescription') }}</span>
                <span class="col-span-1 text-center">{{ t('tools.skillCalls') }}</span>
                <span class="col-span-2 text-center">{{ t('tools.skillStatus') }}</span>
                <span class="col-span-2 text-right">{{ t('tools.skillActions') }}</span>
              </div>
              <div
                v-for="skill in filteredSkills"
                :key="skill.id"
                class="grid grid-cols-1 lg:grid-cols-12 gap-3 lg:gap-4 items-center rounded-2xl border border-amber-100/10 bg-surface-1/82 p-4 transition hover:border-amber-300/25 hover:bg-amber-500/10 mb-2"
              >
                <!-- 技能名 -->
                <div class="lg:col-span-3 cursor-pointer" @click="handleToolClick(skill)">
                  <h3 class="text-sm font-semibold text-stone-100">{{ skill.name }}</h3>
                </div>
                <!-- 描述 -->
                <p class="lg:col-span-4 text-xs text-stone-400 line-clamp-2">{{ skill.description }}</p>
                <!-- 调用次数 -->
                <div class="lg:col-span-1 text-center">
                  <span class="text-xs font-mono text-stone-300">{{ skillStats[skill.id]?.total_calls ?? '-' }}</span>
                </div>
                <!-- 状态 -->
                <div class="lg:col-span-2 text-center">
                  <span
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
                    :class="skill.enabled ? 'bg-emerald-500/10 text-emerald-300' : 'bg-stone-500/10 text-stone-400'"
                  >
                    <span class="w-1.5 h-1.5 rounded-full" :class="skill.enabled ? 'bg-emerald-400' : 'bg-stone-500'"></span>
                    {{ skill.enabled ? t('tools.skillActive') : t('tools.skillArchived') }}
                  </span>
                </div>
                <!-- 操作 -->
                <div class="lg:col-span-2 flex items-center justify-end gap-2">
                  <button
                    @click.stop="toggleArchive(skill.id, skill.enabled)"
                    :disabled="togglingSkillId === skill.id"
                    class="rounded-xl px-2.5 py-1 text-xs font-medium transition disabled:opacity-50"
                    :class="skill.enabled
                      ? 'border border-stone-500/30 text-stone-400 hover:text-amber-300 hover:border-amber-300/30'
                      : 'border border-emerald-500/30 text-emerald-400 hover:text-emerald-300 hover:border-emerald-400/30'"
                  >
                    {{ togglingSkillId === skill.id ? '...' : (skill.enabled ? t('tools.skillArchive') : t('tools.skillActivate')) }}
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="py-12 text-center text-stone-400">{{ t('tools.noSkills') }}</div>
          </div>

          <!-- Tab 3: SkillHub 商店 -->
          <div v-if="activeTab === 'skillhub'">
            <!-- 搜索栏 + 分类过滤 -->
            <div class="flex flex-wrap items-center gap-3 mb-5">
              <div class="flex-1 min-w-[240px] relative">
                <BaseIcon icon="lucide:search" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-stone-500" />
                <input
                  v-model="hubSearchQuery"
                  type="text"
                  :placeholder="t('tools.hubSearchPlaceholder')"
                  class="w-full rounded-2xl border border-amber-100/10 bg-white/[0.04] py-2.5 pl-10 pr-4 text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
                  @keyup.enter="searchHub"
                />
              </div>
              <button
                @click="searchHub"
                :disabled="hubSearching"
                class="rounded-2xl bg-amber-500 px-5 py-2.5 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:bg-stone-700 disabled:text-stone-300"
              >{{ hubSearching ? t('tools.searching') : t('common.search') }}</button>
              <label
                v-if="authStore.user?.role === 'admin'"
                class="flex items-center gap-2 rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-300"
              >
                <span>{{ t('tools.installScope') }}</span>
                <select
                  v-model="installScope"
                  class="rounded-lg border border-amber-100/10 bg-surface-1 px-2 py-1 text-stone-100"
                >
                  <option value="tenant">{{ t('tools.scopeTenant') }}</option>
                  <option value="global">{{ t('tools.scopeGlobal') }}</option>
                </select>
              </label>
            </div>

            <!-- 分类标签 -->
            <div class="flex gap-2 mb-5">
              <button
                @click="hubFilter = 'featured'"
                class="rounded-full px-3 py-1.5 text-xs font-medium transition"
                :class="hubFilter === 'featured' ? 'bg-amber-500 text-stone-950' : 'bg-white/[0.05] text-stone-300 hover:bg-amber-500/10'"
              >{{ t('tools.filterFeatured') }}</button>
              <button
                @click="hubFilter = 'all'"
                class="rounded-full px-3 py-1.5 text-xs font-medium transition"
                :class="hubFilter === 'all' ? 'bg-amber-500 text-stone-950' : 'bg-white/[0.05] text-stone-300 hover:bg-amber-500/10'"
              >{{ t('tools.filterAll') }}</button>
              <button
                @click="hubFilter = 'plugin'"
                class="rounded-full px-3 py-1.5 text-xs font-medium transition"
                :class="hubFilter === 'plugin' ? 'bg-amber-500 text-stone-950' : 'bg-white/[0.05] text-stone-300 hover:bg-amber-500/10'"
              >{{ t('tools.filterPlugin') }}</button>
              <button
                @click="hubFilter = 'prompt'"
                class="rounded-full px-3 py-1.5 text-xs font-medium transition"
                :class="hubFilter === 'prompt' ? 'bg-amber-500 text-stone-950' : 'bg-white/[0.05] text-stone-300 hover:bg-amber-500/10'"
              >{{ t('tools.filterPrompt') }}</button>
            </div>

            <!-- 加载中 -->
            <div v-if="hubSearching && !hubLoaded" class="text-center py-12">
              <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-amber-400 border-t-transparent"></div>
              <p class="mt-3 text-stone-400">{{ t('common.loading') }}</p>
            </div>

            <!-- 目录结果（空搜索词时的默认展示）-->
            <div v-else-if="filteredHubResults.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="pkg in filteredHubResults" :key="pkg.id" class="rounded-[24px] border bg-surface-1/82 p-5 transition"
                :class="pkg.installed ? 'border-amber-300/25' : 'border-amber-100/10'">
                <div class="flex items-start justify-between mb-3">
                  <div>
                    <div class="flex items-center gap-2">
                      <h4 class="font-semibold text-stone-100">{{ pkg.name }}</h4>
                      <!-- 类型标签 -->
                      <span class="rounded-full px-1.5 py-0.5 text-xs" :class="pkg.type === 'plugin' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-200'">
                        {{ pkg.type === 'plugin' ? t('tools.marketToolType') : t('tools.marketPromptType') }}
                      </span>
                      <span v-if="pkg.source" class="rounded-full bg-white/[0.05] px-1.5 py-0.5 text-xs text-stone-400">
                        {{ sourceLabel(pkg.source) }}
                      </span>
                      <span v-if="pkg.installed" class="rounded-full border border-amber-400/20 bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-200">
                        {{ t('tools.installed') }}
                      </span>
                    </div>
                    <p class="mt-1 text-xs text-stone-400">{{ pkg.author }} &middot; v{{ pkg.version }}</p>
                  </div>
                  <button
                    v-if="!pkg.installed"
                    @click="installFromHub(pkg.id)"
                    :disabled="installingId === pkg.id"
                    class="flex-shrink-0 rounded-xl bg-amber-500 px-3 py-1.5 text-sm font-medium text-stone-950 transition hover:bg-amber-400 disabled:bg-stone-700 disabled:text-stone-300"
                  >{{ installingId === pkg.id ? t('tools.installing') : t('common.install') }}</button>
                  <button
                    v-else
                    @click="installFromHub(pkg.id)"
                    :disabled="installingId === pkg.id"
                    class="flex-shrink-0 rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-sm text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10 disabled:bg-stone-800 disabled:text-stone-500"
                  >{{ installingId === pkg.id ? t('tools.installing') : t('tools.reinstall') }}</button>
                </div>

                <p class="mb-2 line-clamp-2 text-sm text-stone-400">{{ pkg.description }}</p>

                <!-- 安装反馈消息 -->
                <div v-if="installMessage?.id === pkg.id" class="mb-3 rounded-2xl p-3 text-sm"
                  :class="installMessage.success ? 'bg-green-900/30 border border-green-700 text-green-300' : 'bg-red-900/30 border border-red-700 text-red-300'">
                  <div class="flex items-start gap-2">
                    <BaseIcon v-if="installMessage.success" icon="lucide:check" :size="16" class="mt-0.5 flex-shrink-0" />
                    <BaseIcon v-else icon="lucide:x" :size="16" class="mt-0.5 flex-shrink-0" />
                    <div>
                      <p class="font-medium text-xs mb-1">{{ installMessage.success ? t('tools.installSuccess') : t('tools.installFailed') }}</p>
                      <p class="opacity-80">{{ installMessage.message }}</p>
                      <p v-if="installMessage.success && installMessage.examplePrompt" class="mt-2 opacity-90 text-xs">
                        {{ t('tools.tryExample') }}: 「{{ installMessage.examplePrompt }}」
                      </p>
                      <TrySkillButton
                        v-if="installMessage.success && installMessage.examplePrompt"
                        :prompt="installMessage.examplePrompt"
                        :skill="pkg.id.split('/').pop()"
                      />
                    </div>
                  </div>
                </div>

                <!-- 标签行 -->
                <div class="flex items-center gap-3 text-xs text-stone-500">
                  <span v-if="pkg.stars" class="flex items-center gap-1">
                    <BaseIcon icon="lucide:star" :size="16" class="text-amber-400 fill-current" />
                    {{ pkg.stars }}
                  </span>
                  <span v-for="tag in pkg.tags.slice(0, 4)" :key="tag" class="rounded-full bg-white/[0.05] px-2 py-0.5">{{ tag }}</span>
                </div>
              </div>
            </div>

            <!-- 空目录 -->
            <div v-else-if="hubLoaded && filteredHubResults.length === 0" class="text-center py-12">
              <BaseIcon icon="lucide:package" :size="64" class="mx-auto mb-3 text-stone-600" />
              <p class="text-stone-400">{{ t('tools.catalogEmpty') }}</p>
            </div>
          </div>
        </div>
      </div>

    <ToolDetailModal v-if="selectedTool" :tool="selectedTool" @close="handleCloseDetail" />
    <AddToolModal v-if="showAddModal" @close="showAddModal = false; loadSkills()" />
    <SkillInstallWizard
      :open="installWizardOpen"
      :state="installWizardState"
      :installing="Boolean(installingId)"
      @close="closeInstallWizard"
      @confirm-permissions="confirmWizardPermissions"
      @skip-setup-install="skipSetupAndInstall"
    />
  </div>
</template>
