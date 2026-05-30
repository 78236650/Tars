<script setup lang="ts">
import { Icon } from '@iconify/vue'

defineProps<{
  icon: string
  size?: number | string
}>()
</script>

<template>
  <Icon :icon="icon" :width="size ?? 18" :height="size ?? 18" />
</template>
