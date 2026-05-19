<script setup lang="ts">
import { ref } from 'vue'
import { memoryApi, providersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const { t } = useI18n()
const authStore = useAuthStore()

const exportTenantId = ref(authStore.user?.tenant_id || 'default')
const exporting = ref(false)
const usageLoading = ref(false)
const usageItems = ref<Array<{
  tenant_id: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  created_at: string
}>>([])

const loadUsage = async () => {
  usageLoading.value = true
  try {
    const resp = await providersApi.getUsage({ limit: 50 })
    usageItems.value = resp.data?.items || []
  } catch (e) {
    console.error('加载 Provider 用量失败', e)
    usageItems.value = []
  } finally {
    usageLoading.value = false
  }
}

const exportMemories = async () => {
  exporting.value = true
  try {
    const data = await memoryApi.exportMemories(exportTenantId.value)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `tars-memories-${exportTenantId.value}-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('导出记忆失败', e)
    alert(t('admin.exportFailed'))
  } finally {
    exporting.value = false
  }
}

loadUsage()
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-8">
    <section class="rounded-[24px] border border-amber-100/10 bg-[#171411]/70 p-6">
      <h2 class="text-lg font-semibold text-stone-100">{{ t('admin.providerUsageTitle') }}</h2>
      <p class="mt-1 text-sm text-stone-500">{{ t('admin.providerUsageHint') }}</p>

      <div class="mt-4 flex justify-end">
        <button
          type="button"
          class="rounded-xl border border-amber-100/10 px-3 py-1.5 text-xs text-stone-300 hover:bg-white/[0.04]"
          @click="loadUsage"
        >
          {{ t('common.refresh') }}
        </button>
      </div>

      <div v-if="usageLoading" class="mt-4 text-sm text-stone-400">{{ t('common.loading') }}</div>
      <div v-else-if="usageItems.length === 0" class="mt-4 text-sm text-stone-500">{{ t('admin.providerUsageEmpty') }}</div>
      <div v-else class="mt-4 overflow-x-auto rounded-2xl border border-amber-100/10">
        <table class="min-w-full text-sm">
          <thead class="bg-white/[0.03] text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th class="px-4 py-3">{{ t('admin.colProvider') }}</th>
              <th class="px-4 py-3">{{ t('admin.colModel') }}</th>
              <th class="px-4 py-3">{{ t('admin.colTokensIn') }}</th>
              <th class="px-4 py-3">{{ t('admin.colTokensOut') }}</th>
              <th class="px-4 py-3">{{ t('admin.colTime') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-amber-100/5 text-stone-300">
            <tr v-for="(row, idx) in usageItems" :key="idx">
              <td class="px-4 py-3">{{ row.provider }}</td>
              <td class="px-4 py-3">{{ row.model }}</td>
              <td class="px-4 py-3 font-mono">{{ row.tokens_in }}</td>
              <td class="px-4 py-3 font-mono">{{ row.tokens_out }}</td>
              <td class="px-4 py-3 text-xs text-stone-500">{{ row.created_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="rounded-[24px] border border-amber-100/10 bg-[#171411]/70 p-6">
      <h2 class="text-lg font-semibold text-stone-100">{{ t('admin.memoryExportTitle') }}</h2>
      <p class="mt-1 text-sm text-stone-500">{{ t('admin.memoryExportHint') }}</p>
      <div class="mt-4 flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1 text-sm text-stone-400">
          {{ t('admin.exportTenantId') }}
          <input
            v-model="exportTenantId"
            class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-stone-100"
          />
        </label>
        <button
          type="button"
          class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950 hover:bg-amber-400 disabled:opacity-50"
          :disabled="exporting"
          @click="exportMemories"
        >
          {{ exporting ? t('admin.exporting') : t('admin.exportMemories') }}
        </button>
      </div>
    </section>
  </div>
</template>
