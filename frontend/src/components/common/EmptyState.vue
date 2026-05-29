<script setup lang="ts">
defineProps<{ text?: string }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 py-12 text-content-muted">
    <slot name="icon" />
    <p class="text-sm">{{ text ?? '暂无数据' }}</p>
  </div>
</template>
