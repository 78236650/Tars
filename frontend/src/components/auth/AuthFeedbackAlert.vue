<script setup lang="ts">
defineProps<{
  message: string
  tone?: 'error' | 'info'
}>()
</script>

<template>
  <div
    class="rounded-2xl border px-4 py-3 text-sm"
    :class="
      tone === 'error'
        ? 'border-rose-400/30 bg-rose-500/10 text-rose-100'
        : 'border-amber-300/20 bg-amber-500/10 text-amber-100'
    "
  >
    {{ message }}
  </div>
</template>
