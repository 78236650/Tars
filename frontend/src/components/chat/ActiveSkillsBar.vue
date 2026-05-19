<script setup lang="ts">
import { useI18n } from '@/i18n'

export interface ActiveSkill {
  id: string
  name: string
}

defineProps<{
  skills: ActiveSkill[]
}>()

const { t } = useI18n()
</script>

<template>
  <div
    v-if="skills.length > 0"
    class="flex flex-wrap items-center gap-2 border-b border-amber-100/10 bg-amber-500/[0.06] px-6 py-2.5"
  >
    <span class="text-xs uppercase tracking-[0.18em] text-amber-200/80">{{ t('chat.activeSkills') }}</span>
    <span
      v-for="skill in skills"
      :key="skill.id"
      class="inline-flex items-center gap-1.5 rounded-full border border-amber-300/20 bg-amber-500/10 px-3 py-1 text-xs text-amber-100"
      :title="skill.id"
    >
      <span>⚡</span>
      <span>{{ skill.name }}</span>
    </span>
  </div>
</template>
