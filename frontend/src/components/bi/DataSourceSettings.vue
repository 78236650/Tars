<template>
  <div class="datasource-settings">
    <div class="header">
      <h2 class="title">数据源管理</h2>
      <button class="btn-primary" @click="showCreateModal = true">+ 新建数据源</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="datasources.length === 0" class="empty">暂无数据源，请点击上方按钮创建</div>
    <div v-else class="datasource-list">
      <div v-for="ds in datasources" :key="ds.id" class="datasource-card">
        <div class="card-header">
          <div class="ds-info">
            <span class="ds-name">{{ ds.name }}</span>
            <span class="ds-type">{{ ds.db_type }}</span>
          </div>
          <div class="ds-actions">
            <button class="btn-icon" title="测试连接" @click="testConnection(ds.id)">🔌</button>
            <button class="btn-icon" title="刷新 Schema" @click="refreshSchema(ds.id)">🔄</button>
            <button class="btn-icon" title="编辑标注" @click="editAnnotations(ds)">📝</button>
            <button class="btn-icon btn-danger" title="删除" @click="deleteDataSource(ds.id)">🗑️</button>
          </div>
        </div>
        <div class="card-body">
          <div class="schema-summary">
            表数量: {{ Object.keys(ds.schema_snapshot.tables || {}).length }}
          </div>
          <div v-if="ds.schema_annotations && Object.keys(ds.schema_annotations).length > 0" class="annotations-summary">
            已标注: {{ Object.keys(ds.schema_annotations).length }} 张表
          </div>
        </div>
      </div>
    </div>

    <!-- 创建数据源弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <h3>新建数据源</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：生产库-订单" />
        </div>
        <div class="form-group">
          <label>数据库类型</label>
          <select v-model="createForm.db_type">
            <option value="mysql">MySQL</option>
            <option value="postgresql">PostgreSQL</option>
            <option value="sqlite">SQLite</option>
            <option value="clickhouse">ClickHouse</option>
            <option value="oracle">Oracle</option>
            <option value="sqlserver">SQL Server</option>
          </select>
        </div>
        <div class="form-group">
          <label>连接 URL</label>
          <input v-model="createForm.connection_url" type="text" placeholder="mysql+pymysql://user:pass@host:3306/db" />
          <div class="hint">
            MySQL: mysql+pymysql://user:pass@host:3306/db<br>
            PostgreSQL: postgresql+psycopg2://user:pass@host:5432/db<br>
            SQLite: sqlite:///path/to/db.db
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreateModal = false">取消</button>
          <button class="btn-primary" :disabled="creating" @click="createDataSource">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 标注编辑器弹窗 -->
    <div v-if="showAnnotatorModal" class="modal-overlay" @click.self="showAnnotatorModal = false">
      <div class="modal modal-large">
        <SchemaAnnotator
          :datasource="selectedDataSource"
          @save="onAnnotationsSave"
          @close="showAnnotatorModal = false"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { biApi } from '@/api'
import type { DataSource } from '@/types'
import SchemaAnnotator from './SchemaAnnotator.vue'

const datasources = ref<DataSource[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const showAnnotatorModal = ref(false)
const creating = ref(false)
const selectedDataSource = ref<DataSource | null>(null)

const createForm = ref({
  name: '',
  db_type: 'mysql',
  connection_url: '',
})

async function loadDataSources() {
  loading.value = true
  try {
    const res = await biApi.listDataSources()
    datasources.value = res.datasources
  } catch (e) {
    alert('加载数据源失败')
  } finally {
    loading.value = false
  }
}

async function createDataSource() {
  if (!createForm.value.name || !createForm.value.connection_url) {
    alert('请填写完整信息')
    return
  }
  creating.value = true
  try {
    await biApi.createDataSource(createForm.value)
    showCreateModal.value = false
    createForm.value = { name: '', db_type: 'mysql', connection_url: '' }
    await loadDataSources()
  } catch (e: any) {
    alert('创建失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

async function deleteDataSource(id: string) {
  if (!confirm('确定删除此数据源？')) return
  try {
    await biApi.deleteDataSource(id)
    await loadDataSources()
  } catch (e) {
    alert('删除失败')
  }
}

async function testConnection(id: string) {
  try {
    const res = await biApi.testConnection(id)
    alert(res.success ? '连接成功' : '连接失败: ' + res.message)
  } catch (e) {
    alert('测试失败')
  }
}

async function refreshSchema(id: string) {
  try {
    await biApi.refreshSchema(id)
    alert('Schema 刷新成功')
    await loadDataSources()
  } catch (e) {
    alert('刷新失败')
  }
}

function editAnnotations(ds: DataSource) {
  selectedDataSource.value = ds
  showAnnotatorModal.value = true
}

async function onAnnotationsSave() {
  showAnnotatorModal.value = false
  await loadDataSources()
}

onMounted(loadDataSources)
</script>

<style scoped>
.datasource-settings {
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

.btn-secondary:hover {
  background: #d1d5db;
}

.datasource-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.datasource-card {
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

.ds-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-name {
  font-weight: 600;
  font-size: 16px;
  color: #1f2937;
}

.ds-type {
  background: #dbeafe;
  color: #1e40af;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.ds-actions {
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

.card-body {
  font-size: 13px;
  color: #6b7280;
}

.schema-summary,
.annotations-summary {
  margin-top: 4px;
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
  width: 720px;
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

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group .hint {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.5;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
