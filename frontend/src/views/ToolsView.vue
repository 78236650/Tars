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
const installingId = ref<string | null>(null)

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
  try {
    await skillhubApi.install(skillId)
    await loadSkills()
  } catch (e) {
    console.error('安装失败:', e)
  } finally {
    installingId.value = null
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

// ========= 操作 =========

const handleToolClick = (tool: any) => {
  selectedTool.value = tool
}

const handleCloseDetail = () => {
  selectedTool.value = null
  loadTools()
  loadSkills()
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
          @click="activeTab = 'builtin'"
          class="px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === 'builtin' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-white'"
        >{{ t('tools.tabBuiltin') }}</button>
        <button
          @click="activeTab = 'skills'"
          class="px-5 py-3 text-sm font-medium transition-colors"
          :class="activeTab === 'skills' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-white'"
        >{{ t('tools.tabSkills') }} ({{ skills.length }})</button>
        <button
          @click="activeTab = 'skillhub'"
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
            <div class="flex gap-3 mb-6">
              <div class="flex-1 relative">
                <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <input
                  v-model="hubSearchQuery"
                  type="text"
                  :placeholder="t('tools.hubSearchPlaceholder')"
                  class="w-full pl-10 pr-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  @keyup.enter="searchHub"
                />
              </div>
              <button
                @click="searchHub"
                :disabled="hubSearching"
                class="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 rounded-lg text-white transition-colors"
              >{{ hubSearching ? t('tools.searching') : t('common.search') }}</button>
            </div>

            <div v-if="hubResults.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="pkg in hubResults" :key="pkg.id" class="bg-slate-800 rounded-xl p-5 border border-slate-700">
                <div class="flex items-start justify-between mb-3">
                  <div>
                    <h4 class="font-semibold text-white">{{ pkg.name }}</h4>
                    <p class="text-xs text-slate-400">{{ pkg.author }} &middot; v{{ pkg.version }}</p>
                  </div>
                  <button
                    @click="installFromHub(pkg.id)"
                    :disabled="installingId === pkg.id"
                    class="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-slate-600 rounded-lg text-white text-sm transition-colors"
                  >{{ installingId === pkg.id ? t('tools.installing') : t('common.install') }}</button>
                </div>
                <p class="text-sm text-slate-400 line-clamp-2 mb-3">{{ pkg.description }}</p>
                <div class="flex items-center gap-3 text-xs text-slate-500">
                  <span v-if="pkg.stars">{{ pkg.stars }} stars</span>
                  <span v-for="tag in pkg.tags.slice(0, 3)" :key="tag" class="px-2 py-0.5 bg-slate-700 rounded">{{ tag }}</span>
                </div>
              </div>
            </div>
            <div v-else-if="!hubSearching" class="text-center py-12 text-slate-400">
              {{ t('tools.hubSearchHint') }}
            </div>
          </div>
        </div>
      </div>
    </main>

    <ToolDetailModal v-if="selectedTool" :tool="selectedTool" @close="handleCloseDetail" />
    <AddToolModal v-if="showAddModal" @close="showAddModal = false; loadSkills()" />
  </div>
</template>
