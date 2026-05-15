<template>
  <div class="knowledge-view">
    <KnowledgeManager />
  </div>
</template>

<script setup lang="ts">
import KnowledgeManager from '@/components/knowledge/KnowledgeManager.vue'
</script>

<style scoped>
.knowledge-view {
  height: 100vh;
  overflow-y: auto;
  background: #f3f4f6;
}
</style>
