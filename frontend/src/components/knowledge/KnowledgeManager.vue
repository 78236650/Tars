<template>
  <div class="knowledge-manager">
    <div class="header">
      <h2 class="title">知识库管理</h2>
      <button class="btn-primary" @click="showCreateModal = true">+ 新建知识库</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="collections.length === 0" class="empty">暂无知识库，请点击上方按钮创建</div>
    <div v-else class="collections-list">
      <div v-for="coll in collections" :key="coll.id" class="collection-card">
        <div class="card-header">
          <div class="coll-info">
            <span class="coll-name">{{ coll.name }}</span>
            <span v-if="coll.description" class="coll-desc">{{ coll.description }}</span>
          </div>
          <div class="coll-actions">
            <button class="btn-icon" title="搜索测试" @click="openSearch(coll)">🔍</button>
            <button class="btn-icon btn-danger" title="删除" @click="deleteCollection(coll.id)">🗑️</button>
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
              <span class="doc-meta">{{ doc.chunk_count }} chunks · {{ doc.status }}</span>
              <button class="btn-icon-small" @click="deleteDocument(coll.id, doc.id)">✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建知识库弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h3>新建知识库</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：产品文档" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="createForm.description" type="text" placeholder="知识库用途描述" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreateModal = false">取消</button>
          <button class="btn-primary" :disabled="creating" @click="createCollection">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 搜索测试弹窗 -->
    <div v-if="showSearchModal" class="modal-overlay" @click.self="showSearchModal = false">
      <div class="modal modal-large">
        <h3>搜索测试 - {{ activeCollection?.name }}</h3>
        <div class="search-box">
          <input v-model="searchQuery" type="text" placeholder="输入搜索内容..." @keyup.enter="performSearch" />
          <button class="btn-primary" :disabled="searching" @click="performSearch">
            {{ searching ? '搜索中...' : '搜索' }}
          </button>
        </div>
        <div v-if="searchResults.length > 0" class="search-results">
          <div v-for="(r, idx) in searchResults" :key="idx" class="result-item">
            <div class="result-source">📄 {{ r.source.file_name }} (chunk {{ r.source.chunk_index + 1 }}/{{ r.source.chunk_total }})</div>
            <div class="result-text">{{ r.text }}</div>
            <div class="result-score">相似度: {{ (r.score * 100).toFixed(1) }}%</div>
          </div>
        </div>
        <div v-else-if="searched" class="search-empty">未找到相关内容</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { knowledgeApi } from '@/api'
import type { KnowledgeCollection, KnowledgeDocument } from '@/types'
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
    alert('加载知识库失败')
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
    alert('请填写名称')
    return
  }
  creating.value = true
  try {
    await knowledgeApi.createCollection(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', description: '' }
    await loadCollections()
  } catch (e: any) {
    alert('创建失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

async function deleteCollection(id: string) {
  if (!confirm('确定删除此知识库？其中的所有文档也将被删除。')) return
  try {
    await knowledgeApi.deleteCollection(id)
    await loadCollections()
  } catch (e) {
    alert('删除失败')
  }
}

async function deleteDocument(collectionId: string, docId: string) {
  if (!confirm('确定删除此文档？')) return
  try {
    await knowledgeApi.deleteDocument(collectionId, docId)
    await loadDocuments(collectionId)
  } catch (e) {
    alert('删除失败')
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
    alert('搜索失败')
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
  color: #1f2937;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
  border: none;
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
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  background: white;
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
  color: #1f2937;
}

.coll-desc {
  font-size: 13px;
  color: #6b7280;
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
  background: #f3f4f6;
}

.btn-danger:hover {
  background: #fee2e2;
}

.documents-list {
  margin-top: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: #f9fafb;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 13px;
}

.doc-name {
  flex: 1;
  color: #374151;
}

.doc-meta {
  color: #6b7280;
  font-size: 12px;
}

.btn-icon-small {
  background: none;
  border: none;
  cursor: pointer;
  color: #9ca3af;
  font-size: 12px;
}

.btn-icon-small:hover {
  color: #ef4444;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  width: 480px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-large {
  width: 640px;
}

.modal h3 {
  margin-bottom: 16px;
  font-size: 18px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

.search-box {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-box input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  margin-bottom: 8px;
}

.result-source {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.result-text {
  font-size: 14px;
  color: #1f2937;
  line-height: 1.5;
}

.result-score {
  font-size: 12px;
  color: #10b981;
  margin-top: 4px;
}

.search-empty {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}
</style>
