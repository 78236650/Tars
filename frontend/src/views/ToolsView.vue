<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Sidebar from '@/components/layout/Sidebar.vue'
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
const selectedTool = ref<any>(null)
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

const filteredTools = computed(() => {
  if (!searchQuery.value) return tools.value
  const q = searchQuery.value.toLowerCase()
  return tools.value.filter(item => item.name.toLowerCase().includes(q) || item.description.toLowerCase().includes(q))
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

const handleToolClick = (tool: any) => {
  selectedTool.value = tool
}

const handleCloseDetail = () => {
  selectedTool.value = null
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
  <div class="flex h-screen bg-slate-900">
    <Sidebar />

    <main class="flex-1 flex flex-col">
      <header class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-lg">T</span>
          </div>
          <div>
            <h1 class="text-lg font-semibold text-white">{{ t('tools.title') }}</h1>
            <p class="text-sm text-slate-400">{{ t('tools.subtitle') }}</p>
          </div>
        </div>
        <button
          @click="showAddModal = true"
          class="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
          <span>{{ t('tools.addSkill') }}</span>
        </button>
      </header>

      <!-- Tab 栏 -->
      <div class="flex border-b border-slate-700 px-6">
        <button
          @click="onTabChange('builtin')"
          class="px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === 'builtin' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-white'"
        >{{ t('tools.tabBuiltin') }}</button>
        <button
          @click="onTabChange('skills')"
          class="px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === 'skills' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-white'"
        >{{ t('tools.tabSkills') }} ({{ skills.length }})</button>
        <button
          @click="onTabChange('skillhub')"
          class="px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === 'skillhub' ? 'text-purple-400 border-b-2 border-purple-400' : 'text-slate-400 hover:text-white'"
        >{{ t('tools.tabSkillhub') }}</button>
      </div>

      <div class="flex-1 overflow-y-auto p-6">
        <div class="max-w-6xl mx-auto">

          <!-- 搜索栏（内置工具 + 已安装技能 Tab） -->
          <div v-if="activeTab !== 'skillhub'" class="mb-6">
            <div class="relative">
              <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="t('tools.searchPlaceholder')"
                class="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <!-- Tab 1: 内置工具 -->
          <div v-if="activeTab === 'builtin'">
            <div v-if="loading" class="text-center py-12">
              <div class="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <div v-else-if="filteredTools.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <ToolCard v-for="tool in filteredTools" :key="tool.id" :tool="tool" @click="handleToolClick(tool)" />
            </div>
            <div v-else class="text-center py-12 text-slate-400">{{ t('tools.noTools') }}</div>
          </div>

          <!-- Tab 2: 已安装技能 -->
          <div v-if="activeTab === 'skills'">
            <div v-if="filteredSkills.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div
                v-for="skill in filteredSkills"
                :key="skill.id"
                class="bg-slate-800 rounded-xl p-6 border border-slate-700 hover:border-blue-500 cursor-pointer transition-colors"
                @click="handleToolClick(skill)"
              >
                <div class="flex items-start justify-between mb-3">
                  <h3 class="text-lg font-semibold text-white">{{ skill.name }}</h3>
                  <div class="w-3 h-3 rounded-full" :class="skill.enabled ? 'bg-green-500' : 'bg-slate-500'"></div>
                </div>
                <p class="text-sm text-slate-400 mb-4 line-clamp-2">{{ skill.description }}</p>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs px-2 py-1 rounded-full" :class="skill.type === 'plugin' ? 'bg-green-600/20 text-green-400' : 'bg-purple-600/20 text-purple-400'">
                    {{ skill.type === 'plugin' ? 'Plugin' : 'Prompt' }}
                  </span>
                  <span class="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-300">{{ skill.source }}</span>
                  <span v-if="skill.version" class="text-xs text-slate-500">v{{ skill.version }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-12 text-slate-400">{{ t('tools.noSkills') }}</div>
          </div>

          <!-- Tab 3: SkillHub 商店 -->
          <div v-if="activeTab === 'skillhub'">
            <!-- 搜索栏 + 分类过滤 -->
            <div class="flex flex-wrap items-center gap-3 mb-5">
              <div class="flex-1 min-w-[240px] relative">
                <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <input
                  v-model="hubSearchQuery"
                  type="text"
                  :placeholder="t('tools.hubSearchPlaceholder')"
                  class="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  @keyup.enter="searchHub"
                />
              </div>
              <button
                @click="searchHub"
                :disabled="hubSearching"
                class="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 rounded-lg text-white text-sm transition-colors"
              >{{ hubSearching ? t('tools.searching') : t('common.search') }}</button>
            </div>

            <!-- 分类标签 -->
            <div class="flex gap-2 mb-5">
              <button
                @click="hubFilter = 'all'"
                class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors"
                :class="hubFilter === 'all' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'"
              >{{ t('tools.filterAll') }}</button>
              <button
                @click="hubFilter = 'plugin'"
                class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors"
                :class="hubFilter === 'plugin' ? 'bg-green-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'"
              >{{ t('tools.filterPlugin') }}</button>
              <button
                @click="hubFilter = 'prompt'"
                class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors"
                :class="hubFilter === 'prompt' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'"
              >{{ t('tools.filterPrompt') }}</button>
            </div>

            <!-- 加载中 -->
            <div v-if="hubSearching && !hubLoaded" class="text-center py-12">
              <div class="inline-block w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
              <p class="mt-3 text-slate-400">{{ t('common.loading') }}</p>
            </div>

            <!-- 目录结果（空搜索词时的默认展示）-->
            <div v-else-if="filteredHubResults.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="pkg in filteredHubResults" :key="pkg.id" class="bg-slate-800 rounded-xl p-5 border transition-colors"
                :class="pkg.installed ? 'border-green-700' : 'border-slate-700'">
                <div class="flex items-start justify-between mb-3">
                  <div>
                    <div class="flex items-center gap-2">
                      <h4 class="font-semibold text-white">{{ pkg.name }}</h4>
                      <!-- 类型标签 -->
                      <span class="text-xs px-1.5 py-0.5 rounded-full" :class="pkg.type === 'plugin' ? 'bg-green-600/20 text-green-400' : 'bg-purple-600/20 text-purple-400'">
                        {{ pkg.type === 'plugin' ? 'Tool' : 'Prompt' }}
                      </span>
                      <!-- 已安装标签 -->
                      <span v-if="pkg.installed" class="text-xs px-1.5 py-0.5 rounded-full bg-green-600/20 text-green-400 border border-green-600/30">
                        {{ t('tools.installed') }}
                      </span>
                    </div>
                    <p class="text-xs text-slate-400 mt-1">{{ pkg.author }} &middot; v{{ pkg.version }}</p>
                  </div>
                  <button
                    v-if="!pkg.installed"
                    @click="installFromHub(pkg.id)"
                    :disabled="installingId === pkg.id"
                    class="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-slate-600 rounded-lg text-white text-sm transition-colors flex-shrink-0"
                  >{{ installingId === pkg.id ? t('tools.installing') : t('common.install') }}</button>
                  <button
                    v-else
                    @click="installFromHub(pkg.id)"
                    :disabled="installingId === pkg.id"
                    class="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 disabled:bg-slate-700 rounded-lg text-white text-sm transition-colors flex-shrink-0"
                  >{{ installingId === pkg.id ? t('tools.installing') : t('tools.reinstall') }}</button>
                </div>

                <p class="text-sm text-slate-400 line-clamp-2 mb-2">{{ pkg.description }}</p>

                <!-- 安装反馈消息 -->
                <div v-if="installMessage?.id === pkg.id" class="mb-3 p-3 rounded-lg text-sm"
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
                <div class="flex items-center gap-3 text-xs text-slate-500">
                  <span v-if="pkg.stars" class="flex items-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                    {{ pkg.stars }}
                  </span>
                  <span v-for="tag in pkg.tags.slice(0, 4)" :key="tag" class="px-2 py-0.5 bg-slate-700 rounded-full">{{ tag }}</span>
                </div>
              </div>
            </div>

            <!-- 空目录 -->
            <div v-else-if="hubLoaded && filteredHubResults.length === 0" class="text-center py-12">
              <svg class="w-12 h-12 mx-auto text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
              </svg>
              <p class="text-slate-400">{{ t('tools.catalogEmpty') }}</p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <ToolDetailModal v-if="selectedTool" :tool="selectedTool" @close="handleCloseDetail" />
    <AddToolModal v-if="showAddModal" @close="showAddModal = false; loadSkills()" />
  </div>
</template>
