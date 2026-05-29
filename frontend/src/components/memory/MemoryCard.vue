<script setup lang="ts">
import { computed } from 'vue'
import type { MemoryItem } from '@/types'
import { useI18n } from '@/i18n'

const props = withDefaults(
  defineProps<{
    memory: MemoryItem
    selectable?: boolean
    selected?: boolean
    expanded?: boolean
    showPromote?: boolean
    showPin?: boolean
    showEdit?: boolean
    showDelete?: boolean
  }>(),
  {
    selectable: false,
    selected: false,
    expanded: false,
    showPromote: false,
    showPin: false,
    showEdit: false,
    showDelete: false,
  }
)

const emit = defineEmits<{
  (e: 'toggle-select'): void
  (e: 'toggle-expand'): void
  (e: 'promote'): void
  (e: 'toggle-pin'): void
  (e: 'edit'): void
  (e: 'delete'): void
}>()
const { t } = useI18n()

const displayTime = computed(() => {
  const value = props.memory.event_time || props.memory.created_at || props.memory.updated_at
  if (!value) return t('memory.unknownTime')
  return new Date(value).toLocaleString()
})

const importancePercent = computed(() => Math.max(0, Math.min(100, Math.round((props.memory.importance || 0) * 100))))
</script>

<template>
  <article class="rounded-xl border border-amber-100/10 bg-surface-2/60 p-4">
    <div class="flex items-start gap-3">
      <input
        v-if="selectable"
        :checked="selected"
        type="checkbox"
        class="mt-1 h-4 w-4 rounded border-amber-100/20 bg-surface-2 text-amber-500 accent-amber-500"
        @change="emit('toggle-select')"
      />

      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2 text-xs text-stone-400">
          <span class="rounded-full bg-stone-800/60 px-2 py-1">{{ memory.category }}</span>
          <span>{{ displayTime }}</span>
          <span v-if="memory.pinned" class="rounded-full bg-amber-500/20 px-2 py-1 text-amber-300">{{ t('memory.pinned') }}</span>
          <span class="rounded-full bg-stone-800/60 px-2 py-1">{{ memory.memory_type }}</span>
        </div>

        <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-200">
          {{ expanded ? memory.content : memory.summary || memory.content }}
        </p>

        <div v-if="memory.entity_refs.length" class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="entity in memory.entity_refs"
            :key="entity"
            class="rounded-full bg-amber-500/10 px-2 py-1 text-xs text-amber-300"
          >
            {{ entity }}
          </span>
        </div>

        <div class="mt-3">
          <div class="mb-1 flex items-center justify-between text-xs text-stone-400">
            <span>{{ t('memory.importance') }}</span>
            <span>{{ importancePercent }}%</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-stone-800/60">
            <div class="h-full rounded-full bg-amber-500" :style="{ width: `${importancePercent}%` }"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button
        class="rounded-lg border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-200 transition hover:bg-amber-500/10"
        @click="emit('toggle-expand')"
      >
        {{ expanded ? t('memory.collapseDetail') : t('memory.expandDetail') }}
      </button>
      <button
        v-if="showPromote"
        class="rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-300 transition hover:bg-amber-500/20"
        @click="emit('promote')"
      >
        {{ t('memory.markImportant') }}
      </button>
      <button
        v-if="showPin"
        class="rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-300 transition hover:bg-amber-500/20"
        @click="emit('toggle-pin')"
      >
        {{ memory.pinned ? t('memory.unpin') : t('memory.pinProtect') }}
      </button>
      <button
        v-if="showEdit"
        class="rounded-lg border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-200 transition hover:bg-amber-500/10"
        @click="emit('edit')"
      >
        {{ t('common.edit') }}
      </button>
      <button
        v-if="showDelete"
        class="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300 transition hover:bg-red-500/20"
        @click="emit('delete')"
      >
        {{ t('common.delete') }}
      </button>
    </div>
  </article>
</template>
