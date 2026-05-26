<template>
  <div class="wiki-viewer">
    <div class="wiki-sidebar">
      <h3>{{ t('wiki.title', 'Wiki') }}</h3>
      <ul class="wiki-page-list">
        <li
          v-for="page in pages"
          :key="page.name"
          :class="{ active: page.name === activePage }"
          @click="loadPage(page.name)"
        >
          {{ page.name }}
        </li>
      </ul>
    </div>
    <div class="wiki-content">
      <div v-if="loading" class="wiki-loading">Loading...</div>
      <div v-else-if="content" class="wiki-markdown" v-html="renderedContent" />
      <div v-else class="wiki-empty">{{ t('wiki.selectPage', '选择一个页面查看') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'
import { useI18n } from '@/i18n'

const { t } = useI18n()

const pages = ref<{ name: string }[]>([])
const activePage = ref('')
const content = ref('')
const loading = ref(false)

const renderedContent = computed(() => (content.value ? marked(content.value) : ''))

async function fetchPages() {
  const resp = await fetch('/api/wiki/')
  const data = await resp.json()
  pages.value = data.pages ?? []
}

async function loadPage(name: string) {
  activePage.value = name
  loading.value = true
  try {
    const resp = await fetch(`/api/wiki/${name}`)
    const data = await resp.json()
    content.value = data.content ?? ''
  } finally {
    loading.value = false
  }
}

onMounted(fetchPages)
</script>

<style scoped>
.wiki-viewer {
  display: flex;
  height: 100%;
  min-height: 400px;
}
.wiki-sidebar {
  width: 200px;
  border-right: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  padding: 1rem;
  overflow-y: auto;
}
.wiki-page-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.wiki-page-list li {
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 4px;
}
.wiki-page-list li.active {
  background: var(--bg-active, rgba(255, 255, 255, 0.08));
}
.wiki-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}
.wiki-empty,
.wiki-loading {
  color: var(--text-muted, #94a3b8);
}
</style>
