<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from '@/i18n'

const props = defineProps<{
  prompt?: string
  skill?: string
}>()

const router = useRouter()
const { t } = useI18n()

const goTry = () => {
  const query: Record<string, string> = {}
  if (props.prompt) query.prompt = props.prompt
  if (props.skill) query.skill = props.skill
  router.push({ path: '/', query })
}
</script>

<template>
  <button
    type="button"
    @click="goTry"
    class="mt-2 rounded-xl bg-amber-500/20 border border-amber-400/30 px-3 py-1.5 text-xs font-medium text-amber-200 transition hover:bg-amber-500/30"
  >
    {{ t('tools.tryInChat') }}
  </button>
</template>
