<script setup lang="ts">
import { useI18n } from '@/i18n'
import BaseIcon from '@/components/common/BaseIcon.vue'

defineProps<{
  tool: {
    id: string
    name: string
    icon?: string
    type: string
    source?: string
    status: string
    description: string
    version?: string
  }
}>()

defineEmits<{
  click: [tool: any]
}>()

const { t } = useI18n()

const typeLabel = (type: string) => {
  switch (type) {
    case 'builtin': return 'Tool'
    case 'plugin': return 'Plugin'
    case 'prompt': return 'Prompt'
    default: return type
  }
}

const typeClass = (type: string) => {
  switch (type) {
    case 'builtin': return 'bg-blue-600/20 text-blue-400'
    case 'plugin': return 'bg-green-600/20 text-green-400'
    case 'prompt': return 'bg-purple-600/20 text-purple-400'
    default: return 'bg-slate-600/20 text-slate-400'
  }
}
</script>

<template>
  <div
    class="bg-slate-800 rounded-xl p-6 cursor-pointer hover:bg-slate-750 transition-colors border border-slate-700 hover:border-blue-500"
    @click="$emit('click', tool)"
  >
    <div class="flex items-start justify-between mb-4">
      <div class="text-4xl"><BaseIcon v-if="tool.icon" :icon="tool.icon" :size="36" /><BaseIcon v-else icon="lucide:wrench" :size="36" /></div>
      <div
        class="w-3 h-3 rounded-full"
        :class="tool.status === 'active' ? 'bg-green-500' : 'bg-slate-500'"
      ></div>
    </div>

    <h3 class="text-lg font-semibold text-white mb-2">{{ tool.name }}</h3>
    <p class="text-sm text-slate-400 mb-4 line-clamp-2">{{ tool.description }}</p>

    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-xs px-2 py-1 rounded-full" :class="typeClass(tool.type)">
          {{ typeLabel(tool.type) }}
        </span>
        <span v-if="tool.source && tool.source !== 'builtin'" class="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-300">
          {{ tool.source }}
        </span>
      </div>
      <span class="text-xs text-slate-500">
        {{ tool.status === 'active' ? t('common.enabled') : t('common.disabled') }}
      </span>
    </div>
  </div>
</template>
