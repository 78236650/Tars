<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { memoryApi } from '@/api'
import type { MemoryCompressionStatus, MemoryStats } from '@/types'
import { useI18n } from '@/i18n'
import PersonalityTab from '@/components/memory/PersonalityTab.vue'
import RecentMemoryTab from '@/components/memory/RecentMemoryTab.vue'
import LongtermMemoryTab from '@/components/memory/LongtermMemoryTab.vue'
import AllMemoryTab from '@/components/memory/AllMemoryTab.vue'
import CompressDialog from '@/components/memory/CompressDialog.vue'

const { t } = useI18n()
const tabs = computed(() => [
  { key: 'personality', label: t('memory.tab.personality') },
  { key: 'recent', label: t('memory.tab.recent') },
  { key: 'longterm', label: t('memory.tab.longterm') },
  { key: 'all', label: t('memory.tab.all') },
])

const activeTab = ref<'personality' | 'recent' | 'longterm' | 'all'>('personality')
const stats = ref<MemoryStats | null>(null)
const compressStatus = ref<MemoryCompressionStatus | null>(null)
const compressDialogOpen = ref(false)
const compressing = ref(false)

const pendingBadgeVisible = computed(() => (stats.value?.pending_compression || 0) > 0)

const selectTab = (key: 'personality' | 'recent' | 'longterm' | 'all') => {
  activeTab.value = key
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
        <header class="rounded-3xl border border-amber-100/10 bg-[#1a1511]/82 p-6 shadow-[0_24px_80px_rgba(8,7,5,0.3)]">
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
            @click="selectTab(tab.key as 'personality' | 'recent' | 'longterm' | 'all')"
          >
            {{ tab.label }}
          </button>
        </div>

        <section class="mt-6">
          <PersonalityTab v-if="activeTab === 'personality'" />
          <RecentMemoryTab v-else-if="activeTab === 'recent'" @changed="loadStats" />
          <LongtermMemoryTab v-else-if="activeTab === 'longterm'" @changed="loadStats" />
          <AllMemoryTab v-else @changed="loadStats" />
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
