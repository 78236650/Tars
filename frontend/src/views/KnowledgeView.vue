<template>
  <div class="knowledge-view">
    <div class="knowledge-content">
      <WikiViewer />
    </div>
  </div>
</template>

<script setup lang="ts">
import WikiViewer from '@/components/knowledge/WikiViewer.vue'
</script>

<style scoped>
.knowledge-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: transparent; }
.knowledge-content { flex: 1; min-height: 0; overflow-y: auto; }
</style>
