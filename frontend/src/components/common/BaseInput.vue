<script setup lang="ts">
defineProps<{ modelValue?: string; placeholder?: string }>()
defineEmits<{ 'update:modelValue': [v: string] }>()
</script>

<template>
  <input
    :value="modelValue"
    :placeholder="placeholder"
    class="w-full rounded-card border border-border bg-surface-1 px-3 py-2 text-content-primary placeholder:text-content-muted focus:outline-none focus:ring-2 focus:ring-accent/40"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
