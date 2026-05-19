<template>
  <div class="knowledge-view">
    <div v-if="highlightDocId" class="doc-highlight-banner">
      已定位文档引用：<code>{{ highlightDocId }}</code>
    </div>
    <KnowledgeManager />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import KnowledgeManager from '@/components/knowledge/KnowledgeManager.vue'

const route = useRoute()
const highlightDocId = computed(() => String(route.query.doc_id || '').trim())
</script>

<style scoped>
.knowledge-view {
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.doc-highlight-banner {
  margin: 12px 16px 0;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.25);
  background: rgba(59, 130, 246, 0.08);
  color: #bfdbfe;
  font-size: 13px;
}

.doc-highlight-banner code {
  color: #93c5fd;
}
</style>
