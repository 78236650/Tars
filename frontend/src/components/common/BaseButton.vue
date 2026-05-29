<script setup lang="ts">
defineProps<{ variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; disabled?: boolean }>()
</script>

<template>
  <button
    :class="`btn-${variant ?? 'primary'}`"
    :disabled="disabled"
    class="inline-flex items-center justify-center gap-1.5 rounded-card px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-50 disabled:cursor-not-allowed"
  >
    <slot />
  </button>
</template>
