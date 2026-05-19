<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { skillsApi } from '@/api'
import { useI18n } from '@/i18n'

interface PendingItem {
  skill_id: string
  total_calls: number
  last_called: number
  idle_days: number
}

const { t } = useI18n()
const loading = ref(false)
const items = ref<PendingItem[]>([])
const days = ref(30)
const archivingId = ref<string | null>(null)

const loadPending = async () => {
  loading.value = true
  try {
    const resp = await skillsApi.getPendingArchive(days.value)
    items.value = resp.data?.items || []
  } catch (e) {
    console.error('加载待归档技能失败', e)
    items.value = []
  } finally {
    loading.value = false
  }
}

const archiveOne = async (skillId: string) => {
  archivingId.value = skillId
  try {
    await skillsApi.archive(skillId)
    items.value = items.value.filter(i => i.skill_id !== skillId)
  } catch (e) {
    console.error('归档失败', e)
  } finally {
    archivingId.value = null
  }
}

onMounted(loadPending)

defineExpose({ reload: loadPending })
</script>

<template>
  <section v-if="loading || items.length > 0" class="mb-6 rounded-[24px] border border-amber-100/10 bg-[#171411]/70 p-5">
    <div class="mb-4 flex items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-stone-100">{{ t('tools.pendingArchiveTitle') }}</h3>
        <p class="mt-1 text-xs text-stone-500">{{ t('tools.pendingArchiveHint', { days }) }}</p>
      </div>
      <button
        type="button"
        class="rounded-xl border border-amber-100/10 px-3 py-1.5 text-xs text-stone-300 hover:bg-white/[0.04]"
        @click="loadPending"
      >
        {{ t('common.refresh') }}
      </button>
    </div>

    <div v-if="loading" class="text-sm text-stone-400">{{ t('common.loading') }}</div>
    <div v-else class="space-y-2">
      <div
        v-for="item in items"
        :key="item.skill_id"
        class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-100/10 bg-white/[0.03] px-4 py-3"
      >
        <div>
          <p class="text-sm font-medium text-stone-100">{{ item.skill_id }}</p>
          <p class="text-xs text-stone-500">
            {{ t('tools.pendingArchiveMeta', { calls: item.total_calls, days: item.idle_days }) }}
          </p>
        </div>
        <button
          type="button"
          class="rounded-xl bg-amber-500/15 px-3 py-1.5 text-xs text-amber-200 hover:bg-amber-500/25 disabled:opacity-50"
          :disabled="archivingId === item.skill_id"
          @click="archiveOne(item.skill_id)"
        >
          {{ archivingId === item.skill_id ? t('tools.archiving') : t('tools.archiveNow') }}
        </button>
      </div>
    </div>
  </section>
</template>
