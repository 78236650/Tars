<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { memoryApi } from '@/api'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import type { LongtermMemoryGroup, MemoryItem, MemoryMergeResponse } from '@/types'
import { useI18n } from '@/i18n'
import MemoryCard from './MemoryCard.vue'
import MergePreviewDialog from './MergePreviewDialog.vue'

const emit = defineEmits<{
  (e: 'changed'): void
}>()

const groups = ref<LongtermMemoryGroup[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const collapsedGroups = ref<string[]>([])
const expandedIds = ref<string[]>([])
const selectedIds = ref<string[]>([])
const editingId = ref('')
const editingContent = ref('')
const mergeDialogOpen = ref(false)
const mergeLoading = ref(false)
const mergePreview = ref<MemoryMergeResponse | null>(null)
const { t } = useI18n()

const currentEditingMemory = computed(() => {
  if (!editingId.value) return null
  for (const group of groups.value) {
    const match = group.items.find((item) => item.id === editingId.value)
    if (match) return match
  }
  return null
})

const isGroupCollapsed = (name: string) => collapsedGroups.value.includes(name)
const isExpanded = (id: string) => expandedIds.value.includes(id)
const isSelected = (id: string) => selectedIds.value.includes(id)

const toggleGroup = (name: string) => {
  collapsedGroups.value = isGroupCollapsed(name)
    ? collapsedGroups.value.filter((item) => item !== name)
    : [...collapsedGroups.value, name]
}

const toggleExpanded = (id: string) => {
  expandedIds.value = isExpanded(id)
    ? expandedIds.value.filter((item) => item !== id)
    : [...expandedIds.value, id]
}

const toggleSelected = (id: string) => {
  selectedIds.value = isSelected(id)
    ? selectedIds.value.filter((item) => item !== id)
    : [...selectedIds.value, id]
}

const loadGroups = async () => {
  loading.value = true
  try {
    const response = await memoryApi.getLongterm({ page: page.value, group_by: 'entity' })
    total.value = response.total
    if (page.value === 1) {
      groups.value = response.groups
      return
    }

    const merged = new Map(groups.value.map((group) => [group.group_name, [...group.items]]))
    for (const group of response.groups) {
      const existing = merged.get(group.group_name) || []
      merged.set(group.group_name, [...existing, ...group.items])
    }
    groups.value = Array.from(merged.entries()).map(([group_name, items]) => ({ group_name, items }))
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  page.value = 1
  await loadGroups()
  emit('changed')
}

const loadMore = async () => {
  if (loading.value) return
  const loadedCount = groups.value.reduce((sum, group) => sum + group.items.length, 0)
  if (loadedCount >= total.value) return
  page.value += 1
  await loadGroups()
}

const deleteMemory = async (id: string) => {
  await memoryApi.deleteMemory(id)
  selectedIds.value = selectedIds.value.filter((item) => item !== id)
  await refresh()
}

const togglePin = async (memory: MemoryItem) => {
  await memoryApi.pinMemory(memory.id, !memory.pinned)
  await refresh()
}

const startEditing = (memory: MemoryItem) => {
  editingId.value = memory.id
  editingContent.value = memory.content
}

const closeEditor = () => {
  editingId.value = ''
  editingContent.value = ''
}

const saveEdit = async () => {
  if (!editingId.value) return
  await memoryApi.updateMemory(editingId.value, editingContent.value)
  closeEditor()
  await refresh()
}

const openMergeDialog = () => {
  mergeDialogOpen.value = true
  mergePreview.value = null
}

const createPreview = async () => {
  mergeLoading.value = true
  try {
    mergePreview.value = await memoryApi.mergeMemories(selectedIds.value, true)
  } finally {
    mergeLoading.value = false
  }
}

const confirmMerge = async () => {
  mergeLoading.value = true
  try {
    await memoryApi.mergeMemories(selectedIds.value, false)
    selectedIds.value = []
    mergeDialogOpen.value = false
    mergePreview.value = null
    await refresh()
  } finally {
    mergeLoading.value = false
  }
}

onMounted(() => {
  void loadGroups()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-100/10 bg-[#1a1511]/60 p-4">
      <div>
        <h2 class="text-lg font-semibold text-stone-100">{{ t('memory.longtermTitle') }}</h2>
        <p class="mt-1 text-sm text-stone-400">{{ t('memory.longtermSubtitle') }}</p>
      </div>
      <button
        class="rounded-xl bg-amber-600 px-4 py-3 text-sm font-medium text-stone-950 transition hover:bg-amber-500 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="selectedIds.length < 2"
        @click="openMergeDialog"
      >
        {{ t('memory.mergeCompress') }} {{ selectedIds.length ? `(${selectedIds.length})` : '' }}
      </button>
    </div>

    <div v-if="loading" class="rounded-2xl border border-amber-100/10 bg-[#1a1511]/60 px-4 py-6 text-center text-sm text-stone-400">
      {{ t('memory.loading') }}
    </div>

    <section
      v-for="group in groups"
      :key="group.group_name"
      class="rounded-2xl border border-amber-100/10 bg-[#1a1511]/60 p-4"
    >
      <button class="flex w-full items-center justify-between" @click="toggleGroup(group.group_name)">
        <div class="text-left">
          <h3 class="text-base font-semibold text-stone-100">{{ group.group_name }}</h3>
          <p class="mt-1 text-sm text-stone-400">{{ t('memory.itemsCount', { count: group.items.length }) }}</p>
        </div>
        <span class="text-sm text-stone-400">{{ isGroupCollapsed(group.group_name) ? t('memory.expand') : t('memory.collapse') }}</span>
      </button>

      <div v-if="!isGroupCollapsed(group.group_name)" class="mt-4 space-y-4">
        <div v-for="memory in group.items" :key="memory.id" class="space-y-3">
          <MemoryCard
            :memory="memory"
            :expanded="isExpanded(memory.id)"
            :selected="isSelected(memory.id)"
            selectable
            show-pin
            show-edit
            show-delete
            @toggle-select="toggleSelected(memory.id)"
            @toggle-expand="toggleExpanded(memory.id)"
            @toggle-pin="togglePin(memory)"
            @edit="startEditing(memory)"
            @delete="deleteMemory(memory.id)"
          />

        </div>
      </div>
    </section>

    <div v-if="!loading && !groups.length" class="rounded-2xl border border-amber-100/10 bg-[#1a1511]/60 px-4 py-6 text-center text-sm text-stone-400">
      {{ t('memory.longtermEmpty') }}
    </div>

    <div v-else-if="groups.length" class="flex justify-center">
      <button
        class="rounded-xl border border-amber-100/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-stone-200 transition hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="loading || groups.reduce((sum, group) => sum + group.items.length, 0) >= total"
        @click="loadMore"
      >
        {{
          groups.reduce((sum, group) => sum + group.items.length, 0) >= total
            ? t('memory.allLoaded')
            : (loading ? t('memory.loading') : t('memory.loadMore'))
        }}
      </button>
    </div>

    <MergePreviewDialog
      :open="mergeDialogOpen"
      :loading="mergeLoading"
      :preview="mergePreview"
      :selected-count="selectedIds.length"
      @close="mergeDialogOpen = false"
      @preview="createPreview"
      @confirm="confirmMerge"
    />

    <AppSurfaceDialog
      :open="Boolean(currentEditingMemory)"
      :title="t('memory.editLongtermTitle')"
      :description="currentEditingMemory ? t('memory.editLongtermDescription', { category: currentEditingMemory.category }) : ''"
      size="lg"
      @close="closeEditor"
    >
      <div class="space-y-4">
        <div class="rounded-2xl border border-amber-100/10 bg-[#110f0d] p-4">
          <p class="text-xs uppercase tracking-[0.2em] text-stone-500">{{ t('memory.originalContent') }}</p>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-300">
            {{ currentEditingMemory?.summary || currentEditingMemory?.content }}
          </p>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-stone-200" for="longterm-memory-editor">
            {{ t('memory.editContent') }}
          </label>
          <textarea
            id="longterm-memory-editor"
            v-model="editingContent"
            rows="8"
            class="w-full rounded-2xl border border-amber-100/10 bg-[#110f0d] px-4 py-3 text-sm text-stone-100 outline-none transition-colors focus:border-amber-300/30"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
            @click="closeEditor"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="rounded-2xl bg-amber-400 px-4 py-2 font-medium text-stone-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-stone-600 disabled:text-stone-300"
            :disabled="!editingContent.trim()"
            @click="saveEdit"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>
  </div>
</template>
