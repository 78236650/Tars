<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { memoryApi, adminMemoryApi, type AdminMemoryUser } from '@/api'
import type { MemoryCompressionStatus, MemoryStats, MemoryItem } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import PersonalityTab from '@/components/memory/PersonalityTab.vue'
import RecentMemoryTab from '@/components/memory/RecentMemoryTab.vue'
import LongtermMemoryTab from '@/components/memory/LongtermMemoryTab.vue'
import AllMemoryTab from '@/components/memory/AllMemoryTab.vue'
import MemoryTreeTab from '@/components/memory/MemoryTreeTab.vue'
import CompressDialog from '@/components/memory/CompressDialog.vue'

const authStore = useAuthStore()
const { t } = useI18n()

const isAdmin = computed(() => authStore.user?.role === 'admin')

const tabs = computed(() => {
  const base = [
    { key: 'recent', label: t('memory.tab.recent') },
    { key: 'longterm', label: t('memory.tab.longterm') },
    { key: 'tree', label: t('memory.tab.entity') },
    { key: 'all', label: t('memory.tab.all') },
    { key: 'personality', label: t('memory.tab.personality') },
  ]
  if (isAdmin.value) {
    base.push({ key: 'admin', label: t('memory.tab.admin') })
  }
  return base
})

const activeTab = ref<'recent' | 'longterm' | 'tree' | 'all' | 'personality' | 'admin'>('recent')
const stats = ref<MemoryStats | null>(null)

// v4.0.0: Admin 记忆管理
const adminUsers = ref<AdminMemoryUser[]>([])
const adminUserMemories = ref<MemoryItem[]>([])
const adminSelectedUserId = ref<string | null>(null)
const adminLoadingUsers = ref(false)
const adminLoadingMemories = ref(false)
const adminSharedContent = ref('')
const adminSharedCategory = ref('')
const adminPurging = ref(false)
const adminCreatingShared = ref(false)
const compressStatus = ref<MemoryCompressionStatus | null>(null)
const compressDialogOpen = ref(false)
const compressing = ref(false)
const longtermFocusGroup = ref<string | null>(null)

const pendingBadgeVisible = computed(() => (stats.value?.pending_compression || 0) > 0)

const onOpenLongtermFromTree = (entityId: string) => {
  longtermFocusGroup.value = entityId
  activeTab.value = 'longterm'
}

const onOpenPersonalityFromTree = () => {
  activeTab.value = 'personality'
}

const selectTab = (key: 'personality' | 'recent' | 'longterm' | 'tree' | 'all' | 'admin') => {
  activeTab.value = key
  if (key === 'admin') {
    loadAdminUsers()
  }
}

// v4.0.0: Admin 记忆管理方法
const loadAdminUsers = async () => {
  adminLoadingUsers.value = true
  try {
    const res = await adminMemoryApi.getUsers()
    adminUsers.value = res.users || []
  } catch (e) {
    console.error('加载管理用户失败:', e)
  } finally {
    adminLoadingUsers.value = false
  }
}

const loadAdminUserMemories = async (userId: string) => {
  adminSelectedUserId.value = userId
  adminLoadingMemories.value = true
  try {
    const res = await adminMemoryApi.getUserMemories(userId)
    adminUserMemories.value = res.items || []
  } catch (e) {
    console.error('加载用户记忆失败:', e)
    adminUserMemories.value = []
  } finally {
    adminLoadingMemories.value = false
  }
}

const purgeUserMemories = async (userId: string) => {
  if (!confirm(t('memory.admin.purgeConfirm'))) return
  adminPurging.value = true
  try {
    await adminMemoryApi.purgeUser(userId)
    adminUserMemories.value = []
    await loadAdminUsers()
  } catch (e) {
    console.error('清空失败:', e)
  } finally {
    adminPurging.value = false
  }
}

const createSharedMemory = async () => {
  if (!adminSharedContent.value.trim()) return
  adminCreatingShared.value = true
  try {
    await adminMemoryApi.createShared({
      content: adminSharedContent.value.trim(),
      category: adminSharedCategory.value.trim() || 'general',
    })
    adminSharedContent.value = ''
    adminSharedCategory.value = ''
    await loadAdminUsers()
  } catch (e) {
    console.error('创建共享记忆失败:', e)
  } finally {
    adminCreatingShared.value = false
  }
}

const loadStats = async () => {
  stats.value = await memoryApi.getStats()
}

const loadCompressStatus = async () => {
  compressStatus.value = await memoryApi.getCompressStatus()
}

const openCompressDialog = async () => {
  compressDialogOpen.value = true
  await loadCompressStatus()
}

const runCompress = async () => {
  compressing.value = true
  compressDialogOpen.value = true
  try {
    await memoryApi.compressAll()
    await Promise.all([loadStats(), loadCompressStatus()])
  } finally {
    compressing.value = false
  }
}

onMounted(() => {
  void Promise.all([loadStats(), loadCompressStatus()])
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
    <main class="flex-1 min-h-0 overflow-hidden">
      <div class="h-full overflow-y-auto px-6 py-6">
        <header class="rounded-3xl border border-amber-100/10 bg-surface-2/82 p-6 shadow-[0_24px_80px_rgba(8,7,5,0.3)]">
          <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <div class="flex items-center gap-3">
                <h1 class="text-2xl font-semibold text-stone-100">{{ t('memory.title') }}</h1>
                <span
                  v-if="pendingBadgeVisible"
                  class="rounded-full bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-300"
                >
                  {{ t('memory.pendingCompression', { count: stats?.pending_compression ?? 0 }) }}
                </span>
              </div>
              <p class="mt-2 text-sm text-stone-400">
                {{ t('memory.subtitle') }}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-3">
              <div class="rounded-2xl border border-amber-100/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
                {{ t('memory.total') }} <span class="ml-2 font-semibold text-stone-100">{{ stats?.total ?? 0 }}</span>
              </div>
              <div class="rounded-2xl border border-amber-100/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
                {{ t('memory.recent') }} <span class="ml-2 font-semibold text-stone-100">{{ stats?.recent ?? 0 }}</span>
              </div>
              <div class="rounded-2xl border border-amber-100/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
                {{ t('memory.longterm') }} <span class="ml-2 font-semibold text-stone-100">{{ stats?.longterm ?? 0 }}</span>
              </div>
              <div class="rounded-2xl border border-amber-100/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
                {{ t('memory.lastCompressed') }} <span class="ml-2 font-semibold text-stone-100">{{ stats?.last_compressed_at || t('memory.none') }}</span>
              </div>
              <button
                class="rounded-2xl bg-amber-600 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-amber-500 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="compressing"
                @click="runCompress"
              >
                {{ compressing ? t('memory.compressing') : t('memory.manualCompress') }}
              </button>
              <button
                class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-stone-100 transition hover:border-amber-300/25 hover:bg-amber-500/10"
                @click="openCompressDialog"
              >
                {{ t('memory.viewProgress') }}
              </button>
            </div>
          </div>
        </header>

        <div class="mt-6 flex gap-2">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="rounded-2xl px-4 py-3 text-sm font-medium transition"
            :class="activeTab === tab.key ? 'bg-amber-600 text-stone-950' : 'border border-amber-100/10 bg-[#171310] text-stone-300 hover:bg-amber-500/10'"
            @click="selectTab(tab.key as typeof activeTab)"
          >
            {{ tab.label }}
          </button>
        </div>

        <section class="mt-6">
          <div
            v-if="isAdmin && adminSelectedUserId && (activeTab === 'tree' || activeTab === 'longterm')"
            class="mb-4 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-2 text-sm text-amber-200"
          >
            {{ t('memory.tree.viewingUser', { user: adminSelectedUserId }) }}
          </div>
          <PersonalityTab v-if="activeTab === 'personality'" />
          <RecentMemoryTab v-else-if="activeTab === 'recent'" @changed="loadStats" />
          <LongtermMemoryTab
            v-else-if="activeTab === 'longterm'"
            :focus-group-name="longtermFocusGroup"
            @changed="loadStats"
          />
          <MemoryTreeTab
            v-else-if="activeTab === 'tree'"
            :admin-user-id="isAdmin ? adminSelectedUserId : null"
            @changed="loadStats"
            @open-longterm="onOpenLongtermFromTree"
            @open-personality="onOpenPersonalityFromTree"
          />
          <AllMemoryTab v-else-if="activeTab === 'all'" @changed="loadStats" />
          <!-- v4.0.0: Admin 记忆管理面板 -->
          <div v-else-if="activeTab === 'admin'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- 用户列表 -->
            <div class="lg:col-span-1 rounded-2xl border border-amber-100/10 bg-surface-1/82 p-5">
              <h3 class="text-sm font-medium text-stone-300 mb-3">{{ t('memory.admin.usersTitle') }}</h3>
              <div v-if="adminLoadingUsers" class="text-center py-4 text-xs text-stone-400">
                <div class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"></div>
              </div>
              <div v-else-if="adminUsers.length > 0" class="space-y-1">
                <button
                  v-for="u in adminUsers"
                  :key="u.tenant_id"
                  @click="loadAdminUserMemories(u.tenant_id)"
                  class="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-sm transition"
                  :class="adminSelectedUserId === u.tenant_id
                    ? 'bg-amber-500/15 text-amber-200'
                    : 'text-stone-300 hover:bg-white/[0.04]'"
                >
                  <span class="truncate text-xs">{{ u.username }}</span>
                  <span class="text-xs text-stone-400">{{ t('memory.admin.memoryCount', { count: u.memory_count }) }}</span>
                </button>
              </div>
              <div v-else class="py-4 text-center text-xs text-stone-400">{{ t('memory.admin.noUsers') }}</div>
            </div>

            <!-- 记忆详情 + 操作 -->
            <div class="lg:col-span-2 rounded-2xl border border-amber-100/10 bg-surface-1/82 p-5">
              <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-medium text-stone-300">
                  {{ adminSelectedUserId
                    ? t('memory.admin.memoriesOf', { user: adminSelectedUserId })
                    : t('memory.admin.selectUserHint') }}
                </h3>
                <button
                  v-if="adminSelectedUserId"
                  @click="purgeUserMemories(adminSelectedUserId)"
                  :disabled="adminPurging"
                  class="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 transition hover:bg-rose-500/20 disabled:opacity-50"
                >
                  {{ adminPurging ? '...' : t('memory.admin.purgeUser') }}
                </button>
              </div>
              <div v-if="adminLoadingMemories" class="text-center py-6 text-xs text-stone-400">
                <div class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"></div>
              </div>
              <div v-else-if="adminUserMemories.length > 0" class="space-y-2 max-h-[400px] overflow-y-auto">
                <div
                  v-for="mem in adminUserMemories"
                  :key="mem.id"
                  class="rounded-xl border border-amber-100/10 bg-white/[0.02] p-3"
                >
                  <p class="text-xs text-stone-200 line-clamp-3">{{ mem.content || mem.summary }}</p>
                  <div class="mt-2 flex items-center gap-2 text-[10px] text-stone-500">
                    <span>{{ mem.category || '-' }}</span>
                    <span>·</span>
                    <span>{{ mem.memory_type || '-' }}</span>
                  </div>
                </div>
              </div>
              <div v-else-if="adminSelectedUserId" class="py-6 text-center text-xs text-stone-400">
                {{ t('memory.admin.noUserMemories') }}
              </div>

              <!-- 创建共享记忆 -->
              <div class="mt-6 pt-4 border-t border-amber-100/10">
                <h4 class="text-xs font-medium text-stone-400 mb-2">{{ t('memory.admin.createShared') }}</h4>
                <div class="space-y-2">
                  <textarea
                    v-model="adminSharedContent"
                    :placeholder="t('memory.admin.sharedContentPh')"
                    rows="3"
                    class="w-full rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none resize-none"
                  />
                  <div class="flex items-center gap-2">
                    <input
                      v-model="adminSharedCategory"
                      :placeholder="t('memory.admin.sharedCategoryPh')"
                      class="flex-1 rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-xs text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none"
                    />
                    <button
                      @click="createSharedMemory"
                      :disabled="adminCreatingShared || !adminSharedContent.trim()"
                      class="rounded-xl bg-amber-500 px-4 py-2 text-xs font-medium text-stone-950 transition hover:bg-amber-400 disabled:opacity-50"
                    >
                      {{ adminCreatingShared ? '...' : t('common.create') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <CompressDialog
      :open="compressDialogOpen"
      :status="compressStatus"
      @close="compressDialogOpen = false"
    />
  </div>
</template>
