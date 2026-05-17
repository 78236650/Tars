<template>
  <div class="knowledge-manager">
    <div class="header">
      <h2 class="title">{{ t('knowledge.title') }}</h2>
      <button class="btn-primary" @click="showCreateModal = true">+ {{ t('knowledge.create') }}</button>
    </div>

    <div v-if="loading" class="loading">{{ t('knowledge.loading') }}</div>
    <div v-else-if="collections.length === 0" class="empty">{{ t('knowledge.empty') }}</div>
    <div v-else class="collections-list">
      <div v-for="coll in collections" :key="coll.id" class="collection-card">
        <div class="card-header">
          <div class="coll-info">
            <span class="coll-name">{{ coll.name }}</span>
            <span v-if="coll.description" class="coll-desc">{{ coll.description }}</span>
          </div>
          <div class="coll-actions">
            <button class="btn-icon" :title="t('knowledge.searchTest')" @click="openSearch(coll)">🔍</button>
            <button class="btn-icon btn-danger" :title="t('common.delete')" @click="deleteCollection(coll.id)">🗑️</button>
          </div>
        </div>
        <div class="card-body">
          <DocumentUploader
            :collection-id="coll.id"
            @uploaded="onDocumentUploaded"
          />
          <div class="documents-list">
            <div v-for="doc in getDocuments(coll.id)" :key="doc.id" class="doc-item">
              <span class="doc-name">📄 {{ doc.file_name }}</span>
              <span class="doc-meta">{{ t('knowledge.documentMeta', { count: doc.chunk_count, status: doc.status }) }}</span>
              <button class="btn-icon-small" @click="deleteDocument(coll.id, doc.id)">✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <AppSurfaceDialog
      :open="showCreateModal"
      :title="t('knowledge.createTitle')"
      :description="t('knowledge.createDescription')"
      size="md"
      @close="showCreateModal = false"
    >
      <div class="space-y-4">
        <div class="form-group">
          <label>{{ t('knowledge.nameLabel') }}</label>
          <input v-model="createForm.name" type="text" :placeholder="t('knowledge.namePlaceholder')" />
        </div>
        <div class="form-group">
          <label>{{ t('knowledge.descriptionLabel') }}</label>
          <input v-model="createForm.description" type="text" :placeholder="t('knowledge.descriptionPlaceholder')" />
        </div>
      </div>

      <template #footer>
        <div class="surface-actions">
          <button class="btn-secondary" @click="showCreateModal = false">{{ t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="creating" @click="createCollection">
            {{ creating ? t('knowledge.creating') : t('common.create') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <AppSurfaceDrawer
      :open="showSearchModal"
      :title="t('knowledge.searchTitle', { name: activeCollection?.name ?? '' })"
      :description="t('knowledge.searchDescription')"
      side="right"
      @close="showSearchModal = false"
    >
      <div class="space-y-4">
        <div class="search-box">
          <input v-model="searchQuery" type="text" :placeholder="t('knowledge.searchPlaceholder')" @keyup.enter="performSearch" />
          <button class="btn-primary" :disabled="searching" @click="performSearch">
            {{ searching ? t('knowledge.searching') : t('common.search') }}
          </button>
        </div>
        <div v-if="searchResults.length > 0" class="search-results">
          <div v-for="(r, idx) in searchResults" :key="idx" class="result-item">
            <div class="result-source">{{ t('knowledge.resultSource', { fileName: r.source.file_name, index: r.source.chunk_index + 1, total: r.source.chunk_total }) }}</div>
            <div class="result-text">{{ r.text }}</div>
            <div class="result-score">{{ t('knowledge.similarity', { score: (r.score * 100).toFixed(1) }) }}</div>
          </div>
        </div>
        <div v-else-if="searched" class="search-empty">{{ t('knowledge.searchEmpty') }}</div>
      </div>
    </AppSurfaceDrawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { knowledgeApi } from '@/api'
import type { KnowledgeCollection, KnowledgeDocument } from '@/types'
import { useI18n } from '@/i18n'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import AppSurfaceDrawer from '@/components/common/AppSurfaceDrawer.vue'
import DocumentUploader from './DocumentUploader.vue'

const collections = ref<KnowledgeCollection[]>([])
const documentsMap = reactive<Record<string, KnowledgeDocument[]>>({})
const loading = ref(false)
const showCreateModal = ref(false)
const showSearchModal = ref(false)
const creating = ref(false)
const activeCollection = ref<KnowledgeCollection | null>(null)
const searchQuery = ref('')
const searching = ref(false)
const searched = ref(false)
const searchResults = ref<any[]>([])
const { t } = useI18n()

const createForm = ref({ name: '', description: '' })

async function loadCollections() {
  loading.value = true
  try {
    const res = await knowledgeApi.listCollections()
    collections.value = res.collections
    for (const coll of res.collections) {
      loadDocuments(coll.id)
    }
  } catch (e) {
    alert(t('knowledge.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadDocuments(collectionId: string) {
  try {
    const res = await knowledgeApi.listDocuments(collectionId)
    documentsMap[collectionId] = res.documents
  } catch (e) {
    documentsMap[collectionId] = []
  }
}

function getDocuments(collectionId: string): KnowledgeDocument[] {
  return documentsMap[collectionId] || []
}

async function createCollection() {
  if (!createForm.value.name) {
    alert(t('knowledge.fillName'))
    return
  }
  creating.value = true
  try {
    await knowledgeApi.createCollection(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', description: '' }
    await loadCollections()
  } catch (e: any) {
    alert(t('knowledge.createFailed', { message: e.response?.data?.detail || e.message }))
  } finally {
    creating.value = false
  }
}

async function deleteCollection(id: string) {
  if (!confirm(t('knowledge.deleteCollectionConfirm'))) return
  try {
    await knowledgeApi.deleteCollection(id)
    await loadCollections()
  } catch (e) {
    alert(t('knowledge.deleteFailed'))
  }
}

async function deleteDocument(collectionId: string, docId: string) {
  if (!confirm(t('knowledge.deleteDocumentConfirm'))) return
  try {
    await knowledgeApi.deleteDocument(collectionId, docId)
    await loadDocuments(collectionId)
  } catch (e) {
    alert(t('knowledge.deleteFailed'))
  }
}

function onDocumentUploaded(collectionId: string) {
  loadDocuments(collectionId)
}

function openSearch(coll: KnowledgeCollection) {
  activeCollection.value = coll
  searchQuery.value = ''
  searchResults.value = []
  searched.value = false
  showSearchModal.value = true
}

async function performSearch() {
  if (!searchQuery.value.trim() || !activeCollection.value) return
  searching.value = true
  searched.value = false
  try {
    const res = await knowledgeApi.queryCollection(activeCollection.value.id, searchQuery.value.trim(), 5)
    searchResults.value = res.results
    searched.value = true
  } catch (e) {
    alert(t('knowledge.searchFailed'))
  } finally {
    searching.value = false
  }
}

onMounted(loadCollections)
</script>

<style scoped>
.knowledge-manager {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #f5f0e8;
}

.btn-primary {
  background: #d97706;
  color: #0c0b09;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.btn-primary:hover {
  background: #f59e0b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: rgba(255,255,255,0.06);
  color: #d6d3d1;
  border: 1px solid rgba(255,255,255,0.08);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.collections-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.collection-card {
  border: 1px solid rgba(245, 158, 11, 0.12);
  border-radius: 12px;
  padding: 16px;
  background: rgba(255,255,255,0.03);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.coll-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.coll-name {
  font-weight: 600;
  font-size: 16px;
  color: #e7e5e4;
}

.coll-desc {
  font-size: 13px;
  color: #78716c;
}

.coll-actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  font-size: 16px;
}

.btn-icon:hover {
  background: rgba(255,255,255,0.06);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.15);
}

.documents-list {
  margin-top: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 13px;
}

.doc-name {
  flex: 1;
  color: #a8a29e;
}

.doc-meta {
  color: #78716c;
  font-size: 12px;
}

.btn-icon-small {
  background: none;
  border: none;
  cursor: pointer;
  color: #78716c;
  font-size: 12px;
}

.btn-icon-small:hover {
  color: #ef4444;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #78716c;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #d6d3d1;
}

.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.form-group input:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
}

.surface-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.search-box {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-box input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-size: 14px;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  margin-bottom: 8px;
}

.result-source {
  font-size: 12px;
  color: #fbbf24;
  margin-bottom: 4px;
}

.result-text {
  font-size: 14px;
  color: #a8a29e;
  line-height: 1.5;
}

.result-score {
  font-size: 12px;
  color: #d97706;
  margin-top: 4px;
}

.search-empty {
  text-align: center;
  padding: 40px;
  color: #78716c;
}
</style>
