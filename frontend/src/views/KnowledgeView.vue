<template>
  <div class="knowledge-view">
    <div v-if="highlightDocId" class="doc-highlight-banner">
      已定位文档引用：<code>{{ highlightDocId }}</code>
    </div>
    <el-tabs v-model="activeTab" class="knowledge-tabs">
      <el-tab-pane :label="t('knowledge.title', '知识库')" name="knowledge">
        <KnowledgeManager />
      </el-tab-pane>
      <el-tab-pane label="Wiki" name="wiki">
        <WikiViewer />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '@/i18n'

const { t } = useI18n()
import KnowledgeManager from '@/components/knowledge/KnowledgeManager.vue'
import WikiViewer from '@/components/knowledge/WikiViewer.vue'

const activeTab = ref('knowledge')

const route = useRoute()
const highlightDocId = computed(() => String(route.query.doc_id || '').trim())
</script>

<style scoped>
.knowledge-view {
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.knowledge-tabs {
  height: 100%;
}

.knowledge-tabs :deep(.el-tabs__content) {
  height: calc(100% - 40px);
  overflow: auto;
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
