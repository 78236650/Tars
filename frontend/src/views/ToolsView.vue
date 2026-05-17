<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import ToolCard from '@/components/tools/ToolCard.vue'
import ToolDetailModal from '@/components/tools/ToolDetailModal.vue'
import AddToolModal from '@/components/tools/AddToolModal.vue'
import { toolsApi, skillsApi, skillhubApi } from '@/api'
import { useI18n } from '@/i18n'
import type { Tool, SkillItem, SkillHubPackage } from '@/types'

const activeTab = ref<'builtin' | 'skills' | 'skillhub'>('builtin')
const loading = ref(false)
const searchQuery = ref('')
const { t } = useI18n()

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
// SkillHub
const hubResults = ref<SkillHubPackage[]>([])
const hubSearchQuery = ref('')
const hubSearching = ref(false)
const hubLoaded = ref(false)
const installingId = ref<string | null>(null)
const installMessage = ref<{ id: string; success: boolean; message: string } | null>(null)
const hubFilter = ref<'all' | 'plugin' | 'prompt'>('all')

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

const installFromHub = async (skillId: string) => {
  installingId.value = skillId
  installMessage.value = null
  try {
    const resp = await skillhubApi.install(skillId)
    const data = resp.data
    installMessage.value = {
      id: skillId,
      success: true,
      message: data.usage || t('tools.installSuccess'),
    }
    // 更新已安装列表和目录状态
    await loadSkills()
    await refreshCatalogStatus()
  } catch (e: any) {
    installMessage.value = {
      id: skillId,
      success: false,
      message: e?.response?.data?.detail || t('tools.installFailed'),
    }
  } finally {
    installingId.value = null
  }
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
  if (hubFilter.value !== 'all') {
    results = results.filter(pkg => pkg.type === hubFilter.value)
  }
  return results
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
  if (tab === 'skillhub' && !hubLoaded.value) {
    loadCatalog()
  }
}

onMounted(() => {
  loadTools()
  loadSkills()
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
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
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
              <svg class="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
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

          <!-- Tab 2: 已安装技能 -->
          <div v-if="activeTab === 'skills'">
            <div v-if="filteredSkills.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div
                v-for="skill in filteredSkills"
                :key="skill.id"
                class="cursor-pointer rounded-[24px] border border-amber-100/10 bg-[#171411]/82 p-6 transition hover:border-amber-300/25 hover:bg-amber-500/10"
                @click="handleToolClick(skill)"
              >
                <div class="flex items-start justify-between mb-3">
                  <h3 class="text-lg font-semibold text-stone-100">{{ skill.name }}</h3>
                  <div class="h-3 w-3 rounded-full" :class="skill.enabled ? 'bg-emerald-400' : 'bg-stone-600'"></div>
                </div>
                <p class="mb-4 line-clamp-2 text-sm text-stone-400">{{ skill.description }}</p>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="rounded-full px-2 py-1 text-xs" :class="skill.type === 'plugin' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-200'">
                    {{ skill.type === 'plugin' ? t('tools.pluginType') : t('tools.promptType') }}
                  </span>
                  <span class="rounded-full bg-white/[0.05] px-2 py-1 text-xs text-stone-300">{{ skill.source }}</span>
                  <span v-if="skill.version" class="text-xs text-stone-500">v{{ skill.version }}</span>
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
                <svg class="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
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
            </div>

            <!-- 分类标签 -->
            <div class="flex gap-2 mb-5">
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
              <div v-for="pkg in filteredHubResults" :key="pkg.id" class="rounded-[24px] border bg-[#171411]/82 p-5 transition"
                :class="pkg.installed ? 'border-amber-300/25' : 'border-amber-100/10'">
                <div class="flex items-start justify-between mb-3">
                  <div>
                    <div class="flex items-center gap-2">
                      <h4 class="font-semibold text-stone-100">{{ pkg.name }}</h4>
                      <!-- 类型标签 -->
                      <span class="rounded-full px-1.5 py-0.5 text-xs" :class="pkg.type === 'plugin' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-200'">
                        {{ pkg.type === 'plugin' ? t('tools.marketToolType') : t('tools.marketPromptType') }}
                      </span>
                      <!-- 已安装标签 -->
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
                    <svg v-if="installMessage.success" class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    <svg v-else class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                    <div>
                      <p class="font-medium text-xs mb-1">{{ installMessage.success ? t('tools.installSuccess') : t('tools.installFailed') }}</p>
                      <p class="opacity-80">{{ installMessage.message }}</p>
                    </div>
                  </div>
                </div>

                <!-- 标签行 -->
                <div class="flex items-center gap-3 text-xs text-stone-500">
                  <span v-if="pkg.stars" class="flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                    {{ pkg.stars }}
                  </span>
                  <span v-for="tag in pkg.tags.slice(0, 4)" :key="tag" class="rounded-full bg-white/[0.05] px-2 py-0.5">{{ tag }}</span>
                </div>
              </div>
            </div>

            <!-- 空目录 -->
            <div v-else-if="hubLoaded && filteredHubResults.length === 0" class="text-center py-12">
              <svg class="mx-auto mb-3 h-12 w-12 text-stone-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
              </svg>
              <p class="text-stone-400">{{ t('tools.catalogEmpty') }}</p>
            </div>
          </div>
        </div>
      </div>

    <ToolDetailModal v-if="selectedTool" :tool="selectedTool" @close="handleCloseDetail" />
    <AddToolModal v-if="showAddModal" @close="showAddModal = false; loadSkills()" />
  </div>
</template>
