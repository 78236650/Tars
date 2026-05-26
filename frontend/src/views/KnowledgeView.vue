<template>
  <div class="knowledge-view">
    <div v-if="highlightDocId" class="doc-highlight-banner">
      已定位文档引用：<code>{{ highlightDocId }}</code>
    </div>

    <div class="knowledge-header">
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="knowledge-content">
      <KnowledgeManager v-if="activeTab === 'knowledge'" />
      <WikiViewer v-else-if="activeTab === 'wiki'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '@/i18n'
import KnowledgeManager from '@/components/knowledge/KnowledgeManager.vue'
import WikiViewer from '@/components/knowledge/WikiViewer.vue'

const { t } = useI18n()
const activeTab = ref<'knowledge' | 'wiki'>('knowledge')

const tabs = computed(() => [
  { key: 'knowledge' as const, label: t('knowledge.title', '知识库') },
  { key: 'wiki' as const, label: t('wiki.title', 'Wiki') },
])

const route = useRoute()
const highlightDocId = computed(() => String(route.query.doc_id || '').trim())
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: transparent;
}

.knowledge-header {
  flex-shrink: 0;
  padding: 12px 16px 0;
}

.tabs {
  display: flex;
  gap: 8px;
}

.tab-btn {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #d6d3d1;
}

.tab-btn.active {
  background: rgba(217, 119, 6, 0.16);
  color: #fbbf24;
  font-weight: 500;
}

.knowledge-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
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
