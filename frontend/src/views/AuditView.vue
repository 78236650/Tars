<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { auditApi, type AuditLogItem } from '@/api'
import { useI18n } from '@/i18n'

const { t } = useI18n()

const logs = ref<AuditLogItem[]>([])
const loading = ref(false)
const errorMessage = ref('')
const page = ref(1)
const pageSize = 50
const total = ref(0)

const filterAction = ref('')
const filterUserId = ref('')
const filterActionGroup = ref('')

const actionGroups = [
  { value: '', labelKey: 'audit.groupAll' },
  { value: 'skill', labelKey: 'audit.groupSkill' },
  { value: 'tool', labelKey: 'audit.groupTool' },
  { value: 'bi', labelKey: 'audit.groupBi' },
  { value: 'auth', labelKey: 'audit.groupAuth' },
  { value: 'memory', labelKey: 'audit.groupMemory' },
]

const totalPages = computed(() => Math.ceil(total.value / pageSize))

const loadLogs = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const params: Record<string, string | number> = {
      page: page.value,
      page_size: pageSize,
    }
    if (filterAction.value) params.action = filterAction.value
    if (filterUserId.value) params.user_id = filterUserId.value
    if (filterActionGroup.value) params.action_group = filterActionGroup.value

    const res = await auditApi.getLogs(params)
    logs.value = res.items || []
    total.value = res.total || 0
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number; data?: { detail?: string } } })?.response?.status
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    if (status === 403) {
      errorMessage.value = detail || t('audit.forbidden')
    } else {
      errorMessage.value = detail || t('audit.loadFailed')
    }
    logs.value = []
    total.value = 0
    console.error('加载审计日志失败:', e)
  } finally {
    loading.value = false
  }
}

const goPage = (p: number) => {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  loadLogs()
}

const visiblePages = computed(() => {
  const pages: number[] = []
  const start = Math.max(1, page.value - 2)
  const end = Math.min(totalPages.value, page.value + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

const formatTime = (ts: string) => {
  if (!ts) return '-'
  try {
    const d = new Date(ts)
    return d.toLocaleString()
  } catch {
    return ts
  }
}

// 已知操作类型的翻译
const actionLabels: Record<string, string> = {
  login: 'audit.actionLogin',
  logout: 'audit.actionLogout',
  tool_call: 'audit.actionToolCall',
  'tool_call:success': 'audit.actionToolCall',
  'tool_call:failed': 'audit.actionToolCallFailed',
  session_create: 'audit.actionSessionCreate',
  session_delete: 'audit.actionSessionDelete',
  'memory:write': 'audit.actionMemoryWrite',
  'memory:delete': 'audit.actionMemoryDelete',
  'memory:promote': 'audit.actionMemoryPromote',
  'memory:purge': 'audit.actionMemoryPurge',
  skill_install: 'audit.actionSkillInstall',
  skill_uninstall: 'audit.actionSkillUninstall',
  permission_denied: 'audit.actionPermDenied',
  config_change: 'audit.actionConfigChange',
  user_create: 'audit.actionUserCreate',
  user_delete: 'audit.actionUserDelete',
}

const getActionLabel = (action: string) => {
  const key = actionLabels[action]
  return key ? t(key) : action
}

const skillResourceLink = (log: AuditLogItem) => {
  if (log.action !== 'skill_install' && log.action !== 'skill_uninstall') return null
  const skillId = log.resource?.split(':').slice(1).join(':') || log.detail
  if (!skillId) return '/tools'
  return `/tools?skill=${encodeURIComponent(skillId)}`
}

onMounted(() => {
  loadLogs()
})
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
    <main class="flex-1 min-h-0 overflow-hidden">
      <div class="h-full overflow-y-auto px-6 py-6">
        <!-- Header -->
        <header class="rounded-3xl border border-amber-100/10 bg-[#1a1511]/82 p-6 shadow-[0_24px_80px_rgba(8,7,5,0.3)]">
          <div class="flex flex-col gap-2">
            <h1 class="text-2xl font-semibold text-stone-100">{{ t('audit.title') }}</h1>
            <p class="text-sm text-stone-400">{{ t('audit.subtitle') }}</p>
          </div>
        </header>

        <!-- 筛选条件 -->
        <div class="mt-6 flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2">
            <label class="text-xs text-stone-400">{{ t('audit.filterGroup') }}</label>
            <select
              v-model="filterActionGroup"
              class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-xs text-stone-100 focus:border-amber-300/30 focus:outline-none"
            >
              <option v-for="g in actionGroups" :key="g.value" :value="g.value">{{ t(g.labelKey) }}</option>
            </select>
          </div>
          <div class="flex items-center gap-2">
            <label class="text-xs text-stone-400">{{ t('audit.filterAction') }}</label>
            <input
              v-model="filterAction"
              :placeholder="t('audit.actionPlaceholder')"
              class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-xs text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none w-40"
            />
          </div>
          <div class="flex items-center gap-2">
            <label class="text-xs text-stone-400">{{ t('audit.filterUser') }}</label>
            <input
              v-model="filterUserId"
              :placeholder="t('audit.userPlaceholder')"
              class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-1.5 text-xs text-stone-100 placeholder:text-stone-500 focus:border-amber-300/30 focus:outline-none w-40"
            />
          </div>
          <button
            @click="page = 1; loadLogs()"
            class="rounded-xl bg-amber-500 px-4 py-2 text-xs font-medium text-stone-950 transition hover:bg-amber-400"
          >
            {{ t('common.search') }}
          </button>
        </div>

        <div
          v-if="errorMessage"
          class="mt-4 rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200"
        >
          {{ errorMessage }}
        </div>

        <!-- 日志表格 -->
        <div class="mt-4 overflow-x-auto rounded-2xl border border-amber-100/10">
          <div v-if="loading" class="py-12 text-center text-stone-400">
            <div class="inline-block h-6 w-6 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"></div>
          </div>
          <table v-else-if="logs.length > 0" class="w-full text-sm">
            <thead class="border-b border-amber-100/10">
              <tr class="text-left text-xs font-medium text-stone-400 uppercase tracking-[0.05em]">
                <th class="px-4 py-3">{{ t('audit.colTime') }}</th>
                <th class="px-4 py-3">{{ t('audit.colUser') }}</th>
                <th class="px-4 py-3">{{ t('audit.colAction') }}</th>
                <th class="px-4 py-3">{{ t('audit.colResource') }}</th>
                <th class="px-4 py-3">{{ t('audit.colDetail') }}</th>
                <th class="px-4 py-3">{{ t('audit.colIp') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="log in logs"
                :key="log.id"
                class="border-b border-amber-100/[0.04] transition hover:bg-amber-500/[0.03]"
              >
                <td class="px-4 py-3 text-xs text-stone-300 whitespace-nowrap">{{ formatTime(log.timestamp) }}</td>
                <td class="px-4 py-3 text-xs text-stone-300 font-mono">{{ log.user_id }}</td>
                <td class="px-4 py-3 text-xs">
                  <span class="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-200 whitespace-nowrap">
                    {{ getActionLabel(log.action) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-xs text-stone-400 max-w-[140px] truncate">
                  <router-link
                    v-if="skillResourceLink(log)"
                    :to="skillResourceLink(log)!"
                    class="text-amber-300 hover:text-amber-200 underline-offset-2 hover:underline"
                  >
                    {{ log.resource || '-' }}
                  </router-link>
                  <span v-else>{{ log.resource || '-' }}</span>
                </td>
                <td class="px-4 py-3 text-xs text-stone-400 max-w-[200px] truncate">{{ log.detail || '-' }}</td>
                <td class="px-4 py-3 text-xs text-stone-500 font-mono">{{ log.ip_address || '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="py-12 text-center text-stone-400">{{ t('audit.noLogs') }}</div>
        </div>

        <!-- 分页 -->
        <div v-if="totalPages > 1" class="mt-4 flex items-center justify-center gap-1">
          <button
            @click="goPage(1)"
            :disabled="page === 1"
            class="rounded-lg px-2 py-1.5 text-xs text-stone-400 hover:text-stone-100 disabled:opacity-30 transition"
          >
            ««
          </button>
          <button
            @click="goPage(page - 1)"
            :disabled="page === 1"
            class="rounded-lg px-2 py-1.5 text-xs text-stone-400 hover:text-stone-100 disabled:opacity-30 transition"
          >
            «
          </button>
          <button
            v-for="p in visiblePages"
            :key="p"
            @click="goPage(p)"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="p === page ? 'bg-amber-500 text-stone-950' : 'text-stone-400 hover:text-stone-100'"
          >
            {{ p }}
          </button>
          <button
            @click="goPage(page + 1)"
            :disabled="page >= totalPages"
            class="rounded-lg px-2 py-1.5 text-xs text-stone-400 hover:text-stone-100 disabled:opacity-30 transition"
          >
            »
          </button>
          <button
            @click="goPage(totalPages)"
            :disabled="page >= totalPages"
            class="rounded-lg px-2 py-1.5 text-xs text-stone-400 hover:text-stone-100 disabled:opacity-30 transition"
          >
            »»
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
