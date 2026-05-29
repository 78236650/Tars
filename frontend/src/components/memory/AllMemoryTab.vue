<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { memoryApi } from '@/api'
import type { MemoryItem } from '@/types'
import { useI18n } from '@/i18n'
import MemoryCard from './MemoryCard.vue'

const emit = defineEmits<{
  (e: 'changed'): void
}>()

const items = ref<MemoryItem[]>([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const query = ref('')
const category = ref('')
const memoryType = ref('')
const expandedIds = ref<string[]>([])
const listRef = ref<HTMLElement | null>(null)
const { t } = useI18n()

const categories = ['all', 'fact', 'decision', 'domain_knowledge', 'general', 'project_record']
const memoryTypes = ['all', 'episodic', 'longterm', 'compressed']

const isExpanded = (id: string) => expandedIds.value.includes(id)

const toggleExpanded = (id: string) => {
  expandedIds.value = isExpanded(id)
    ? expandedIds.value.filter((item) => item !== id)
    : [...expandedIds.value, id]
}

const loadMemories = async (reset = false) => {
  if (loading.value) return
  loading.value = true
  try {
    const targetPage = reset ? 1 : page.value
    const response = await memoryApi.getAll({
      page: targetPage,
      q: query.value,
      cat: category.value === 'all' ? '' : category.value,
      memory_type: memoryType.value === 'all' ? '' : memoryType.value,
    })
    total.value = response.total
    if (reset) {
      items.value = response.items
      page.value = 2
    } else {
      items.value = [...items.value, ...response.items]
      page.value += 1
    }
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  await loadMemories(true)
  emit('changed')
}

const handleScroll = async () => {
  const element = listRef.value
  if (!element || loading.value) return
  const nearBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 80
  if (nearBottom && items.value.length < total.value) {
    await loadMemories(false)
  }
}

const deleteMemory = async (id: string) => {
  await memoryApi.deleteMemory(id)
  await refresh()
}

const togglePin = async (memory: MemoryItem) => {
  await memoryApi.pinMemory(memory.id, !memory.pinned)
  await refresh()
}

const promoteMemory = async (id: string) => {
  await memoryApi.promoteMemory(id)
  await refresh()
}

onMounted(() => {
  void loadMemories(true)
})
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-4 rounded-2xl border border-amber-100/10 bg-surface-2/60 p-4 lg:grid-cols-[1fr,220px,180px,140px]">
      <input
        v-model="query"
        type="text"
        class="rounded-xl border border-amber-100/10 bg-surface-0 px-4 py-3 text-sm text-stone-100 outline-none focus:border-amber-400/50"
        :placeholder="t('memory.searchAll')"
        @keyup.enter="refresh"
      />
      <select
        v-model="category"
        class="rounded-xl border border-amber-100/10 bg-surface-0 px-4 py-3 text-sm text-stone-100 outline-none focus:border-amber-400/50"
        @change="refresh"
      >
        <option v-for="item in categories" :key="item" :value="item">
          {{ item === 'all' ? t('memory.allCategories') : item }}
        </option>
      </select>
      <select
        v-model="memoryType"
        class="rounded-xl border border-amber-100/10 bg-surface-0 px-4 py-3 text-sm text-stone-100 outline-none focus:border-amber-400/50"
        @change="refresh"
      >
        <option v-for="item in memoryTypes" :key="item" :value="item">
          {{ item === 'all' ? t('memory.allTypes') : item }}
        </option>
      </select>
      <button
        class="rounded-xl bg-amber-600 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-amber-500"
        @click="refresh"
      >
        {{ t('memory.search') }}
      </button>
    </div>

    <div
      ref="listRef"
      class="max-h-[65vh] space-y-4 overflow-y-auto pr-1"
      @scroll.passive="handleScroll"
    >
      <MemoryCard
        v-for="memory in items"
        :key="memory.id"
        :memory="memory"
        :expanded="isExpanded(memory.id)"
        show-promote
        show-pin
        show-delete
        @toggle-expand="toggleExpanded(memory.id)"
        @promote="promoteMemory(memory.id)"
        @toggle-pin="togglePin(memory)"
        @delete="deleteMemory(memory.id)"
      />

      <div v-if="loading" class="rounded-xl border border-amber-100/10 bg-surface-2/60 px-4 py-6 text-center text-sm text-stone-400">
        {{ t('memory.loading') }}
      </div>
      <div v-else-if="!items.length" class="rounded-xl border border-amber-100/10 bg-surface-2/60 px-4 py-6 text-center text-sm text-stone-400">
        {{ t('memory.allEmpty') }}
      </div>
    </div>
  </div>
</template>
