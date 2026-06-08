<template>
  <div class="wiki-viewer">
    <div class="wiki-sidebar">
      <h3 class="wiki-title">Wiki</h3>
      <div class="wiki-search">
        <input v-model="searchQuery" type="text" placeholder="搜索..." @keyup.enter="doSearch" @input="onSearchInput" />
        <button v-if="searchQuery" class="btn-clear" @click="clearSearch">✕</button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="r in searchResults" :key="r.page_name" class="search-item" @click="loadPage(r.page_name)">
          <span class="si-name">{{ formatName(r.page_name) }}</span>
          <span class="si-score">{{ (r.score * 100).toFixed(0) }}%</span>
        </div>
      </div>
      <div v-else class="wiki-tree">
        <div v-for="cat in tree" :key="cat.key" class="tree-category">
          <div class="tree-cat-header" @click="toggleExpanded(cat.key)">
            <span class="tree-arrow">{{ isExpanded(cat.key) ? '▾' : '▸' }}</span>
            <span class="tree-cat-icon">{{ cat.icon }}</span>
            <span class="tree-cat-label">{{ cat.label }}</span>
            <span class="tree-cat-count">{{ cat.children?.length || cat.pages?.length || 0 }}</span>
          </div>
          <div v-if="isExpanded(cat.key)" class="tree-cat-body">
            <template v-if="cat.children">
              <div v-for="sub in cat.children" :key="sub.key" class="tree-subgroup">
                <div class="tree-sub-header" @click="toggleExpanded(sub.key)">
                  <span class="tree-arrow">{{ isExpanded(sub.key) ? '▾' : '▸' }}</span>
                  <span class="tree-sub-label">{{ sub.label }}</span>
                  <span class="tree-sub-count">{{ sub.pages?.length || 0 }}</span>
                </div>
                <div v-if="isExpanded(sub.key)" class="tree-pages">
                  <div v-for="p in sub.pages" :key="p.name" :class="['tree-page', { active: p.name === activePage }]" @click="loadPage(p.name)">{{ formatName(p.name) }}</div>
                </div>
              </div>
            </template>
            <div v-else class="tree-pages">
              <div v-for="p in cat.pages" :key="p.name" :class="['tree-page', { active: p.name === activePage }]" @click="loadPage(p.name)">{{ formatName(p.name) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="wiki-content">
      <div v-if="loading" class="wiki-loading">加载中...</div>
      <div v-else-if="editing" class="wiki-edit">
        <textarea v-model="editContent" class="wiki-edit-area" />
        <div class="wiki-edit-actions">
          <button class="btn-save" @click="saveEdit">保存</button>
          <button class="btn-cancel" @click="editing = false">取消</button>
        </div>
      </div>
      <div v-else-if="content" class="wiki-view">
        <div class="wiki-actions">
          <span class="wiki-page-title">{{ activePage }}</span>
          <div class="wiki-action-btns">
            <a :href="downloadUrl" :download="activePage + '.md'" class="btn-download" title="下载 Markdown">⬇</a>
            <button class="btn-edit" @click="startEdit">编辑</button>
            <button class="btn-delete" @click="confirmDelete">删除</button>
          </div>
        </div>
        <div v-if="showDeleteConfirm" class="delete-confirm">
          <span>确认删除「{{ activePage }}」？</span>
          <button class="btn-del-yes" @click="doDelete">确认删除</button>
          <button class="btn-cancel" @click="showDeleteConfirm = false">取消</button>
        </div>
        <div class="wiki-markdown" v-html="renderedContent" />
        <div v-if="sources.length > 0" class="wiki-sources">
          <div class="ws-header" @click="sourcesExpanded = !sourcesExpanded">
            <span class="tree-arrow">{{ sourcesExpanded ? '▾' : '▸' }}</span>
            <span class="ws-title">来源记忆</span>
            <span class="ws-count">{{ sources.length }}</span>
          </div>
          <div v-if="sourcesExpanded" class="ws-body">
            <div v-for="s in sources" :key="s.memory_id" class="ws-item" :class="{ missing: !s.exists }">
              <span class="ws-cat">{{ s.exists ? (s.category || '记忆') : '已删除' }}</span>
              <span class="ws-content">{{ s.exists ? s.content : `记忆 ${s.memory_id} 已不存在` }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="wiki-empty">选择一个页面查看</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'

interface WikiPage { name: string }
interface TreeNode { key: string; label: string; icon: string; pages?: WikiPage[]; children?: TreeNode[] }

const CATS = [
  { key: 'meeting', label: '会议纪要', icon: '🎙️', match: (n: string) => n.startsWith('meeting-') },
  { key: 'insight', label: '鉴数知识', icon: '📊', match: (n: string) => n.startsWith('insight-') },
  { key: 'memory', label: '对话精华', icon: '🧠', match: (n: string) => n.startsWith('memory-') },
  { key: 'upload', label: '文档上传', icon: '📄', match: () => true },
]

const pages = ref<WikiPage[]>([])
// 独立的展开状态，不受 computed 重建影响
const expandedState = ref<Record<string, boolean>>({})
function isExpanded(key: string, defaultVal = true): boolean {
  if (key in expandedState.value) return expandedState.value[key]
  return defaultVal
}
function toggleExpanded(key: string) {
  expandedState.value = { ...expandedState.value, [key]: !isExpanded(key) }
}
const activePage = ref('')
const content = ref('')
const loading = ref(false)
const searchQuery = ref('')
const searchResults = ref<{ page_name: string; snippet: string; score: number }[]>([])
const editing = ref(false)
const editContent = ref('')
const showDeleteConfirm = ref(false)
interface WikiSource { memory_id: string; exists: boolean; category: string | null; content: string | null }
const sources = ref<WikiSource[]>([])
const sourcesExpanded = ref(true)
let searchTimer: ReturnType<typeof setTimeout> | null = null
const renderedContent = computed(() => content.value ? marked(content.value) : '')
const downloadUrl = computed(() => content.value ? URL.createObjectURL(new Blob([content.value], { type: 'text/markdown' })) : '#')

function formatName(n: string) { return n.replace(/-/g, ' ').replace(/^meeting /, '') }

const tree = computed<TreeNode[]>(() => {
  const cats: TreeNode[] = []
  const remaining = new Set(pages.value.map(p => p.name))
  for (const cat of CATS.slice(0, -1)) {
    const matched = pages.value.filter(p => cat.match(p.name) && remaining.has(p.name))
    if (!matched.length) continue
    matched.forEach(p => remaining.delete(p.name))
    if (cat.key === 'meeting') {
      cats.push({ key: cat.key, label: cat.label, icon: cat.icon, children: [{ key: 'meeting-all', label: '全部会议', icon: '', pages: matched }] })
    } else if (cat.key === 'insight') {
      const g: Record<string, WikiPage[]> = {}
      for (const p of matched) { const k = p.name.replace(/^insight-/, '').split('-')[0] || '通用'; if (!g[k]) g[k] = []; g[k].push(p) }
      cats.push({ key: cat.key, label: cat.label, icon: cat.icon, children: Object.entries(g).map(([k, ps]) => ({ key: `insight-${k}`, label: k, icon: '', pages: ps })) })
    } else {
      cats.push({ key: cat.key, label: cat.label, icon: cat.icon, pages: matched })
    }
  }
  const rest = pages.value.filter(p => remaining.has(p.name))
  if (rest.length) {
    const g: Record<string, WikiPage[]> = {}
    for (const p of rest) { const k = p.name.split('-')[0] || '其他'; if (!g[k]) g[k] = []; g[k].push(p) }
    const entries = Object.entries(g)
    const singles: WikiPage[] = []; const children: TreeNode[] = []
    for (const [k, ps] of entries) { if (ps.length === 1) singles.push(ps[0]); else children.push({ key: `upload-${k}`, label: k, icon: '', pages: ps }) }
    if (!children.length) cats.push({ key: 'upload', label: '文档上传', icon: '📄', pages: singles })
    else { for (const p of singles) children.push({ key: `upload-${p.name}`, label: p.name, icon: '', pages: [p] }); cats.push({ key: 'upload', label: '文档上传', icon: '📄', children }) }
  }
  return cats
})

async function fetchPages() { const r = await fetch('/api/wiki/'); pages.value = (await r.json()).pages ?? [] }
async function loadPage(name: string) { activePage.value = name; loading.value = true; editing.value = false; searchResults.value = []; searchQuery.value = ''; sources.value = []; try { const r = await fetch(`/api/wiki/${name}`); content.value = (await r.json()).content ?? ''; fetchSources(name) } finally { loading.value = false } }
async function fetchSources(name: string) { try { const r = await fetch(`/api/wiki/${name}/sources`); if (!r.ok) { sources.value = []; return }; sources.value = (await r.json()).sources ?? [] } catch { sources.value = [] } }
function onSearchInput() { if (searchTimer) clearTimeout(searchTimer); searchTimer = setTimeout(doSearch, 300) }
async function doSearch() { const q = searchQuery.value.trim(); if (!q) { searchResults.value = []; return }; try { const r = await fetch(`/api/wiki/search?q=${encodeURIComponent(q)}&top_k=8`); searchResults.value = (await r.json()).results ?? [] } catch { searchResults.value = [] } }
function clearSearch() { searchQuery.value = ''; searchResults.value = [] }
function startEdit() { editContent.value = content.value; editing.value = true }
async function saveEdit() { if (!activePage.value) return; try { await fetch(`/api/wiki/${activePage.value}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: editContent.value }) }); content.value = editContent.value; editing.value = false } catch (e) { console.error('Wiki save failed:', e) } }
function confirmDelete() { showDeleteConfirm.value = true }
async function doDelete() { if (!activePage.value) return; try { await fetch(`/api/wiki/${activePage.value}`, { method: 'DELETE' }); showDeleteConfirm.value = false; content.value = ''; activePage.value = ''; await fetchPages() } catch (e) { console.error('Wiki delete failed:', e) } }
onMounted(fetchPages)
</script>

<style scoped>
.wiki-viewer { display: flex; height: 100%; min-height: 400px; }
.wiki-sidebar { width: 240px; min-width: 200px; border-right: 1px solid rgba(255,255,255,0.08); display: flex; flex-direction: column; overflow-y: auto; background: rgba(0,0,0,0.12); }
.wiki-title { padding: 14px 14px 0; margin: 0; font-size: 14px; color: #a8a29e; font-weight: 500; }
.wiki-search { display: flex; gap: 4px; padding: 10px 14px; }
.wiki-search input { flex: 1; padding: 5px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: #d6d3d1; font-size: 12px; outline: none; }
.wiki-search input:focus { border-color: rgba(245,158,11,0.3); }
.btn-clear { background: none; border: none; color: #78716c; cursor: pointer; font-size: 14px; padding: 0 4px; }
.search-results { padding: 0 14px; }
.search-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.search-item:hover { background: rgba(255,255,255,0.04); }
.si-name { color: #d6d3d1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.si-score { color: #78716c; font-size: 10px; flex-shrink: 0; margin-left: 6px; }
.wiki-tree { padding: 4px 0 14px; }
.tree-category { margin-bottom: 2px; }
.tree-cat-header { display: flex; align-items: center; gap: 4px; padding: 7px 14px; cursor: pointer; user-select: none; transition: background 0.15s; }
.tree-cat-header:hover { background: rgba(255,255,255,0.03); }
.tree-arrow { width: 14px; font-size: 10px; color: #78716c; text-align: center; flex-shrink: 0; }
.tree-cat-icon { font-size: 13px; flex-shrink: 0; }
.tree-cat-label { font-size: 12px; font-weight: 500; color: #d6d3d1; flex: 1; }
.tree-cat-count { font-size: 10px; color: #57534e; background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 8px; }
.tree-cat-body { padding-left: 14px; }
.tree-subgroup { margin-bottom: 1px; }
.tree-sub-header { display: flex; align-items: center; gap: 4px; padding: 5px 10px; cursor: pointer; font-size: 11px; color: #a8a29e; border-radius: 3px; }
.tree-sub-header:hover { background: rgba(255,255,255,0.03); }
.tree-sub-label { flex: 1; }
.tree-sub-count { font-size: 9px; color: #57534e; }
.tree-pages { padding-left: 16px; }
.tree-page { padding: 4px 8px; font-size: 11px; color: #a8a29e; cursor: pointer; border-radius: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: background 0.12s; }
.tree-page:hover { background: rgba(255,255,255,0.05); color: #d6d3d1; }
.tree-page.active { background: rgba(217,119,6,0.12); color: #fbbf24; font-weight: 500; }
.wiki-content { flex: 1; padding: 20px 28px; overflow-y: auto; }
.wiki-actions { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.wiki-page-title { font-size: 12px; color: #78716c; }
.wiki-action-btns { display: flex; gap: 6px; }
.btn-edit { padding: 3px 10px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: #a8a29e; cursor: pointer; font-size: 12px; }
.btn-edit:hover { background: rgba(255,255,255,0.08); }
.btn-download { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 4px; border: 1px solid rgba(96,165,250,0.2); background: rgba(96,165,250,0.06); color: #93c5fd; cursor: pointer; font-size: 14px; text-decoration: none; }
.btn-download:hover { background: rgba(96,165,250,0.15); }
.btn-delete { padding: 3px 10px; border-radius: 4px; border: 1px solid rgba(239,68,68,0.2); background: rgba(239,68,68,0.06); color: #f87171; cursor: pointer; font-size: 12px; }
.btn-delete:hover { background: rgba(239,68,68,0.15); }
.delete-confirm { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding: 8px 14px; border-radius: 6px; border: 1px solid rgba(239,68,68,0.2); background: rgba(239,68,68,0.06); font-size: 13px; color: #fca5a5; }
.btn-del-yes { padding: 3px 12px; border-radius: 4px; border: none; background: #dc2626; color: #fff; cursor: pointer; font-size: 12px; }
.btn-cancel { padding: 3px 12px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1); background: transparent; color: #a8a29e; cursor: pointer; font-size: 12px; }
.wiki-edit-area { width: 100%; min-height: 400px; padding: 12px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); color: #d6d3d1; font-family: monospace; font-size: 13px; resize: vertical; }
.wiki-edit-actions { margin-top: 8px; display: flex; gap: 8px; }
.btn-save { padding: 5px 14px; border-radius: 4px; border: none; background: #d97706; color: #fff; cursor: pointer; font-size: 12px; }
.wiki-empty, .wiki-loading { color: #78716c; font-size: 14px; }
.wiki-markdown { color: #d6d3d1; line-height: 1.8; font-size: 15px; max-width: 800px; }
.wiki-markdown :deep(h1) { font-size: 1.6em; font-weight: 600; color: #fbbf24; margin: 0 0 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.wiki-markdown :deep(h2) { font-size: 1.3em; font-weight: 600; color: #e5e5e5; margin: 28px 0 12px; }
.wiki-markdown :deep(h3) { font-size: 1.1em; font-weight: 500; color: #e5e5e5; margin: 22px 0 10px; }
.wiki-markdown :deep(p) { margin: 0 0 12px; }
.wiki-markdown :deep(strong) { color: #f5f5f4; font-weight: 600; }
.wiki-markdown :deep(a) { color: #fbbf24; }
.wiki-markdown :deep(blockquote) { margin: 12px 0; padding: 8px 16px; border-left: 3px solid #d97706; background: rgba(217,119,6,0.06); color: #a8a29e; border-radius: 0 6px 6px 0; }
.wiki-markdown :deep(code) { font-family: monospace; font-size: 0.9em; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: #fbbf24; }
.wiki-markdown :deep(pre) { margin: 12px 0; padding: 14px 18px; border-radius: 8px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); overflow-x: auto; }
.wiki-markdown :deep(pre code) { padding: 0; background: none; color: #d6d3d1; font-size: 0.85em; line-height: 1.6; }
.wiki-markdown :deep(table) { width: 100%; margin: 14px 0; border-collapse: collapse; font-size: 0.9em; }
.wiki-markdown :deep(th) { padding: 8px 14px; text-align: left; font-weight: 600; color: #e5e5e5; background: rgba(255,255,255,0.05); border-bottom: 2px solid rgba(255,255,255,0.1); }
.wiki-markdown :deep(td) { padding: 8px 14px; border-bottom: 1px solid rgba(255,255,255,0.06); color: #a8a29e; }
.wiki-markdown :deep(tr:hover td) { background: rgba(255,255,255,0.03); }
.wiki-sources { max-width: 800px; margin: 28px 0 0; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); }
.ws-header { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.ws-title { font-size: 12px; font-weight: 500; color: #a8a29e; }
.ws-count { font-size: 10px; color: #57534e; background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 8px; }
.ws-body { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.ws-item { display: flex; gap: 8px; padding: 8px 12px; border-radius: 6px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); font-size: 12px; }
.ws-item.missing { opacity: 0.5; }
.ws-cat { flex-shrink: 0; color: #93c5fd; font-size: 10px; padding: 1px 8px; height: fit-content; border-radius: 8px; background: rgba(96,165,250,0.1); }
.ws-content { color: #a8a29e; line-height: 1.6; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }

</style>
