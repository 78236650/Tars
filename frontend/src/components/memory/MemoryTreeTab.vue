<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { memoryApi } from '@/api'
import type {
  EntityRelationsResponse,
  MemoryEntityGraphResponse,
  MemoryItem,
  MemoryTreeNode as TreeNode,
  MemoryTreeResponse,
  MemoryTreeSearchHit,
} from '@/types'
import { useI18n } from '@/i18n'
import MemoryCard from './MemoryCard.vue'
import MemoryTreeNodeRow from './MemoryTreeNode.vue'
import EntityRelationMiniGraph from './EntityRelationMiniGraph.vue'
import MemoryTreeVirtualList from './MemoryTreeVirtualList.vue'
import MemoryEntityForceGraph from './MemoryEntityForceGraph.vue'
import { flattenMemoryTree } from './memoryTreeFlatten'

const props = defineProps<{
  adminUserId?: string | null
}>()

const emit = defineEmits<{
  (e: 'changed'): void
  (e: 'open-longterm', entityId: string): void
  (e: 'open-personality'): void
}>()

const { t } = useI18n()

const LARGE_TREE_THRESHOLD = 120
const VIRTUAL_SCROLL_THRESHOLD = 40

type TreeViewMode = 'entity' | 'provenance' | 'graph'

const viewMode = ref<TreeViewMode>('entity')
const largeTreeHint = ref(false)
const loading = ref(false)
const treeData = ref<MemoryTreeResponse | null>(null)
const graphData = ref<MemoryEntityGraphResponse | null>(null)
const graphLoading = ref(false)
const expandedIds = ref<Set<string>>(new Set())
const selectedId = ref<string | null>(null)
const selectedKind = ref<string | null>(null)
const relations = ref<EntityRelationsResponse | null>(null)
const relationsLoading = ref(false)
const memoryDetail = ref<MemoryItem | null>(null)
const memoryLoading = ref(false)

const searchQuery = ref('')
const searchHits = ref<MemoryTreeSearchHit[]>([])
const searchLoading = ref(false)
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const collectExpandableIds = (nodes: TreeNode[]): string[] => {
  const ids: string[] = []
  const walk = (list: TreeNode[]) => {
    for (const node of list) {
      if (node.children.length > 0) {
        ids.push(node.id)
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return ids
}

const findNodeById = (nodes: TreeNode[], id: string): TreeNode | null => {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = findNodeById(node.children, id)
    if (found) return found
  }
  return null
}

const findPathToNode = (nodes: TreeNode[], targetId: string, path: string[] = []): string[] | null => {
  for (const node of nodes) {
    const nextPath = [...path, node.id]
    if (node.id === targetId) return nextPath
    const found = findPathToNode(node.children, targetId, nextPath)
    if (found) return found
  }
  return null
}

const computeDefaultExpanded = (nodes: TreeNode[], treeNodeCount?: number) => {
  const all = collectExpandableIds(nodes)
  const heavy = (treeNodeCount ?? all.length) > LARGE_TREE_THRESHOLD
  if (viewMode.value === 'provenance') {
    largeTreeHint.value = false
    return new Set(all)
  }
  if (heavy) {
    largeTreeHint.value = true
    return new Set(nodes.filter((n) => n.children.length > 0).map((n) => n.id))
  }
  largeTreeHint.value = false
  return new Set(all)
}

const loadGraph = async () => {
  graphLoading.value = true
  try {
    graphData.value = await memoryApi.getTreeGraph(props.adminUserId || undefined)
  } catch (e) {
    console.error(e)
    graphData.value = null
  } finally {
    graphLoading.value = false
  }
}

const loadTree = async () => {
  loading.value = true
  try {
    treeData.value = await memoryApi.getTree({
      view: viewMode.value === 'graph' ? 'entity' : viewMode.value,
      user_id: props.adminUserId || undefined,
    })
    expandedIds.value = computeDefaultExpanded(
      treeData.value.nodes,
      treeData.value.stats.tree_node_count
    )
  } catch (e) {
    console.error(e)
    treeData.value = null
  } finally {
    loading.value = false
  }
}

const setViewMode = (mode: TreeViewMode) => {
  if (viewMode.value === mode) return
  viewMode.value = mode
  selectedId.value = null
  selectedKind.value = null
  relations.value = null
  memoryDetail.value = null
  searchQuery.value = ''
  searchHits.value = []
  if (mode === 'graph') void loadGraph()
  else void loadTree()
}

const flatTreeRows = computed(() =>
  treeData.value ? flattenMemoryTree(treeData.value.nodes, expandedIds.value) : []
)

const useVirtualTree = computed(() => flatTreeRows.value.length >= VIRTUAL_SCROLL_THRESHOLD)

const loadEntityRelations = async (entityId: string) => {
  relationsLoading.value = true
  try {
    relations.value = await memoryApi.getTreeRelations(
      entityId,
      props.adminUserId || undefined
    )
  } catch (e) {
    console.error(e)
  } finally {
    relationsLoading.value = false
  }
}

const toggleExpand = (id: string) => {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

const expandAll = () => {
  if (!treeData.value) return
  expandedIds.value = new Set(collectExpandableIds(treeData.value.nodes))
}

const collapseAll = () => {
  expandedIds.value = new Set()
}

const selectNode = async (node: TreeNode) => {
  if (node.kind === 'more') return
  selectedId.value = node.id
  selectedKind.value = node.kind
  relations.value = null
  memoryDetail.value = null

  if (node.kind === 'entity') {
    await loadEntityRelations(node.id)
    return
  }

  if (node.kind === 'memory' || node.kind === 'compressed') {
    memoryLoading.value = true
    try {
      memoryDetail.value = await memoryApi.getMemory(node.id)
    } catch (e) {
      console.error(e)
    } finally {
      memoryLoading.value = false
    }
  }
}

const runSearch = () => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(async () => {
    const q = searchQuery.value.trim()
    if (!q) {
      searchHits.value = []
      return
    }
    searchLoading.value = true
    try {
      const res = await memoryApi.searchTree({
        q,
        view: viewMode.value === 'graph' ? 'entity' : viewMode.value,
        user_id: props.adminUserId || undefined,
      })
      searchHits.value = res.items
    } catch (e) {
      console.error(e)
      searchHits.value = []
    } finally {
      searchLoading.value = false
    }
  }, 300)
}

const applySearchHit = async (hit: MemoryTreeSearchHit) => {
  if (!treeData.value) return
  const expandPath = hit.path.slice(0, -1)
  expandedIds.value = new Set([...expandedIds.value, ...expandPath])
  const node = findNodeById(treeData.value.nodes, hit.node_id)
  if (node) await selectNode(node)
}

const selectedEntityNode = computed(() => {
  if (selectedKind.value !== 'entity' || !selectedId.value || !treeData.value) return null
  return findNodeById(treeData.value.nodes, selectedId.value)
})

const selectedTreeNode = computed(() => {
  if (!selectedId.value || !treeData.value) return null
  return findNodeById(treeData.value.nodes, selectedId.value)
})

const graphEntityMeta = computed(() => {
  if (selectedKind.value !== 'entity' || !selectedId.value || !graphData.value) return null
  return graphData.value.nodes.find((n) => n.id === selectedId.value) ?? null
})

const subtitleText = computed(() => {
  if (viewMode.value === 'provenance') return t('memory.tree.provenanceSubtitle')
  if (viewMode.value === 'graph') return t('memory.tree.graphSubtitle')
  return t('memory.tree.subtitle')
})

const focusEntityFromGraph = async (entityId: string) => {
  selectedId.value = entityId
  selectedKind.value = 'entity'
  memoryDetail.value = null
  await loadEntityRelations(entityId)
}

const openLongtermForEntity = () => {
  const id = selectedEntityNode.value?.id ?? selectedId.value
  if (!id || selectedKind.value !== 'entity') return
  emit('open-longterm', id)
}

const focusEntityInTree = async (entityId: string) => {
  if (viewMode.value !== 'entity') {
    viewMode.value = 'entity'
    selectedId.value = null
    searchQuery.value = ''
    searchHits.value = []
    await loadTree()
  }
  await nextTick()
  if (!treeData.value) return
  const path = findPathToNode(treeData.value.nodes, entityId)
  if (!path) return
  expandedIds.value = new Set([...expandedIds.value, ...path.slice(0, -1)])
  const node = findNodeById(treeData.value.nodes, entityId)
  if (node) await selectNode(node)
}

const onMemoryChanged = async () => {
  emit('changed')
  const keepId = memoryDetail.value?.id
  if (viewMode.value === 'graph') await loadGraph()
  else await loadTree()
  if (keepId) {
    try {
      memoryDetail.value = await memoryApi.getMemory(keepId)
    } catch {
      memoryDetail.value = null
    }
  }
}

const deleteMemory = async () => {
  if (!memoryDetail.value) return
  if (!window.confirm('确定删除这条记忆？')) return
  await memoryApi.deleteMemory(memoryDetail.value.id)
  memoryDetail.value = null
  selectedId.value = null
  await onMemoryChanged()
}

const togglePin = async () => {
  if (!memoryDetail.value) return
  await memoryApi.pinMemory(memoryDetail.value.id, !memoryDetail.value.pinned)
  await onMemoryChanged()
}

const promoteMemory = async () => {
  if (!memoryDetail.value) return
  await memoryApi.promoteMemory(memoryDetail.value.id)
  await onMemoryChanged()
}

watch(
  () => props.adminUserId,
  () => {
    selectedId.value = null
    searchQuery.value = ''
    searchHits.value = []
    if (viewMode.value === 'graph') void loadGraph()
    else void loadTree()
  }
)

watch(searchQuery, () => runSearch())

onMounted(() => {
  void loadTree()
})

const refreshAll = async () => {
  if (viewMode.value === 'graph') await loadGraph()
  else await loadTree()
}

defineExpose({ refresh: refreshAll })
</script>

<template>
  <div class="flex min-h-[480px] flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-stone-100">{{ t('memory.tree.title') }}</h2>
        <p class="mt-1 text-sm text-stone-400">{{ subtitleText }}</p>
        <div class="mt-3 inline-flex rounded-xl border border-amber-100/10 p-0.5">
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="viewMode === 'entity' ? 'bg-amber-600 text-stone-950' : 'text-stone-400 hover:text-stone-200'"
            @click="setViewMode('entity')"
          >
            {{ t('memory.tree.viewEntity') }}
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="viewMode === 'provenance' ? 'bg-amber-600 text-stone-950' : 'text-stone-400 hover:text-stone-200'"
            @click="setViewMode('provenance')"
          >
            {{ t('memory.tree.viewProvenance') }}
          </button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="viewMode === 'graph' ? 'bg-amber-600 text-stone-950' : 'text-stone-400 hover:text-stone-200'"
            @click="setViewMode('graph')"
          >
            {{ t('memory.tree.viewGraph') }}
          </button>
        </div>
        <p
          v-if="adminUserId"
          class="mt-2 text-xs font-medium text-amber-300/90"
        >
          {{ t('memory.tree.viewingUser', { user: adminUserId }) }}
        </p>
        <div
          v-if="treeData"
          class="mt-2 flex flex-wrap gap-3 text-xs text-stone-400"
        >
          <template v-if="viewMode === 'graph' && graphData">
            <span>{{ t('memory.tree.statsEntities') }}: {{ graphData.stats.node_count }}</span>
            <span>{{ t('memory.tree.statsRelations') }}: {{ graphData.stats.edge_count }}</span>
            <span v-if="graphData.stats.truncated" class="text-amber-300/90">
              {{ t('memory.tree.graphTruncated', { max: graphData.stats.max_edges ?? graphData.stats.edge_count }) }}
            </span>
          </template>
          <template v-else-if="viewMode === 'entity'">
            <span>{{ t('memory.tree.statsEntities') }}: {{ treeData.stats.entity_count }}</span>
            <span>{{ t('memory.tree.statsMemories') }}: {{ treeData.stats.memory_count }}</span>
            <span>{{ t('memory.tree.statsOrphan') }}: {{ treeData.stats.orphan_count }}</span>
          </template>
          <template v-else-if="viewMode === 'provenance'">
            <span>{{ t('memory.tree.viewProvenance') }}: {{ treeData.stats.compressed_count ?? 0 }}</span>
            <span>{{ t('memory.tree.compressedSources') }}: {{ treeData.stats.source_count ?? 0 }}</span>
            <span v-if="(treeData.stats.archived_count ?? 0) > 0">
              {{ t('memory.tree.archivedSource') }}: {{ treeData.stats.archived_count }}
            </span>
          </template>
          <span>{{ t('memory.tree.statsRelations') }}: {{ treeData.stats.relation_count }}</span>
          <span v-if="treeData.stats.tree_node_count != null">
            {{ t('memory.tree.statsNodes') }}: {{ treeData.stats.tree_node_count }}
          </span>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <template v-if="viewMode !== 'graph'">
          <button
            type="button"
            class="rounded-xl border border-amber-100/10 px-3 py-2 text-xs text-stone-300 hover:bg-amber-500/10"
            @click="expandAll"
          >
            {{ t('memory.tree.expandAll') }}
          </button>
          <button
            type="button"
            class="rounded-xl border border-amber-100/10 px-3 py-2 text-xs text-stone-300 hover:bg-amber-500/10"
            @click="collapseAll"
          >
            {{ t('memory.tree.collapseAll') }}
          </button>
        </template>
        <button
          type="button"
          class="rounded-xl bg-amber-600/90 px-3 py-2 text-xs font-medium text-stone-950 hover:bg-amber-500"
          :disabled="loading || graphLoading"
          @click="refreshAll"
        >
          {{ t('memory.tree.refresh') }}
        </button>
      </div>
    </div>

    <p
      v-if="largeTreeHint"
      class="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-amber-200/90"
    >
      {{ t('memory.tree.largeTreeHint') }}
    </p>
    <p
      v-if="useVirtualTree && viewMode !== 'graph'"
      class="rounded-xl border border-amber-100/10 bg-white/[0.02] px-4 py-2 text-xs text-stone-400"
    >
      {{ t('memory.tree.virtualScrollHint') }}
    </p>

    <div
      v-if="viewMode !== 'graph'"
      class="relative max-w-md"
    >
      <input
        v-model="searchQuery"
        type="search"
        class="w-full rounded-xl border border-amber-100/10 bg-black/25 px-4 py-2.5 text-sm text-stone-100 placeholder:text-stone-500 focus:border-amber-400/40 focus:outline-none"
        :placeholder="t('memory.tree.searchPlaceholder')"
      />
      <ul
        v-if="searchQuery.trim() && (searchHits.length || (!searchLoading && searchQuery.trim()))"
        class="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-xl border border-amber-100/15 bg-surface-2 py-1 shadow-lg"
      >
        <li
          v-if="searchLoading"
          class="px-3 py-2 text-xs text-stone-400"
        >
          {{ t('memory.loading') }}
        </li>
        <li
          v-else-if="!searchHits.length"
          class="px-3 py-2 text-xs text-stone-500"
        >
          {{ t('memory.tree.searchNoResults') }}
        </li>
        <template v-else>
          <li
            v-for="hit in searchHits"
            :key="hit.node_id"
          >
            <button
              type="button"
              class="w-full px-3 py-2 text-left text-sm text-stone-200 hover:bg-amber-500/10"
              @click="applySearchHit(hit)"
            >
              <span class="text-xs text-stone-500">{{ hit.kind }}</span>
              <span class="ml-2">{{ hit.label }}</span>
            </button>
          </li>
        </template>
      </ul>
    </div>

    <div
      v-if="viewMode === 'graph'"
      class="grid min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-5"
    >
      <div class="lg:col-span-3">
        <MemoryEntityForceGraph
          :nodes="graphData?.nodes ?? []"
          :edges="graphData?.edges ?? []"
          :loading="graphLoading"
          :selected-id="selectedId"
          @focus-entity="focusEntityFromGraph"
        />
      </div>
      <div
        class="min-h-[280px] rounded-2xl border border-amber-100/10 bg-surface-1/82 p-5 lg:col-span-2"
      >
        <template v-if="!selectedId || selectedKind !== 'entity'">
          <p class="text-sm text-stone-400">{{ t('memory.tree.selectHint') }}</p>
        </template>
        <template v-else>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-stone-100">
                {{ relations?.entity_label || graphEntityMeta?.label || selectedId }}
              </h3>
              <p class="mt-1 font-mono text-xs text-stone-500">{{ selectedId }}</p>
            </div>
            <button
              type="button"
              class="rounded-xl border border-amber-100/15 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-500/20"
              @click="openLongtermForEntity"
            >
              {{ t('memory.tree.openLongterm') }}
            </button>
          </div>
          <p
            v-if="graphEntityMeta"
            class="mt-3 text-sm text-stone-300"
          >
            {{ t('memory.tree.statsMemories') }}: {{ graphEntityMeta.memory_count }}
          </p>
          <p class="mt-4 text-xs font-medium uppercase tracking-wide text-stone-500">
            {{ t('memory.tree.relations') }}
          </p>
          <p
            v-if="relationsLoading"
            class="mt-2 text-sm text-stone-400"
          >
            {{ t('memory.loading') }}
          </p>
          <template v-else-if="relations">
            <EntityRelationMiniGraph
              v-if="relations.outgoing.length || relations.incoming.length"
              :center-label="relations.entity_label"
              :outgoing="relations.outgoing"
              :incoming="relations.incoming"
              @focus-entity="focusEntityFromGraph"
            />
            <p
              v-else
              class="mt-2 text-sm text-stone-500"
            >
              {{ t('memory.tree.noRelations') }}
            </p>
          </template>
        </template>
      </div>
    </div>

    <div
      v-else-if="loading"
      class="flex flex-1 items-center justify-center py-16 text-sm text-stone-400"
    >
      {{ t('memory.loading') }}
    </div>

    <div
      v-else-if="!treeData"
      class="rounded-2xl border border-amber-100/10 bg-surface-1/82 p-8 text-center text-sm text-stone-400"
    >
      {{ t('memory.tree.loadFailed') }}
    </div>

    <div
      v-else
      class="grid min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-5"
    >
      <div
        class="max-h-[560px] rounded-2xl border border-amber-100/10 bg-surface-1/82 p-3 lg:col-span-2"
        :class="useVirtualTree ? 'overflow-hidden' : 'overflow-y-auto'"
      >
        <p
          v-if="treeData.nodes.length === 0"
          class="p-4 text-sm text-stone-400"
        >
          {{ viewMode === 'provenance' ? t('memory.tree.provenanceEmpty') : t('memory.tree.empty') }}
        </p>
        <MemoryTreeVirtualList
          v-else-if="useVirtualTree"
          :rows="flatTreeRows"
          :expanded-ids="expandedIds"
          :selected-id="selectedId"
          @toggle="toggleExpand"
          @select="selectNode"
        />
        <ul
          v-else
          class="space-y-0.5"
        >
          <MemoryTreeNodeRow
            v-for="root in treeData.nodes"
            :key="root.id"
            :node="root"
            :depth="0"
            :expanded-ids="expandedIds"
            :selected-id="selectedId"
            @toggle="toggleExpand"
            @select="selectNode"
          />
        </ul>
      </div>

      <div
        class="min-h-[280px] rounded-2xl border border-amber-100/10 bg-surface-1/82 p-5 lg:col-span-3"
      >
        <template v-if="!selectedId">
          <p class="text-sm text-stone-400">{{ t('memory.tree.selectHint') }}</p>
        </template>

        <template v-else-if="selectedKind === 'entity' && selectedEntityNode">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-stone-100">
                {{ selectedEntityNode.label }}
              </h3>
              <p class="mt-1 font-mono text-xs text-stone-500">{{ selectedEntityNode.id }}</p>
            </div>
            <button
              type="button"
              class="rounded-xl border border-amber-100/15 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-500/20"
              @click="openLongtermForEntity"
            >
              {{ t('memory.tree.openLongterm') }}
            </button>
          </div>
          <p
            v-if="selectedEntityNode.meta.is_ghost"
            class="mt-2 text-xs text-amber-300/90"
          >
            {{ t('memory.tree.ghostHint') }}
          </p>
          <p class="mt-3 text-sm text-stone-300">
            {{
              t('memory.tree.entitySummary', {
                longterm: Number(selectedEntityNode.meta.longterm_count ?? 0),
                recent: Number(selectedEntityNode.meta.recent_count ?? 0),
                compressed: Number(selectedEntityNode.meta.compressed_count ?? 0),
              })
            }}
          </p>

          <div class="mt-6">
            <h4 class="text-xs font-medium uppercase tracking-wide text-stone-500">
              {{ t('memory.tree.relations') }}
            </h4>
            <p
              v-if="relationsLoading"
              class="mt-2 text-xs text-stone-400"
            >
              {{ t('memory.loading') }}
            </p>
            <template v-else-if="relations && (relations.outgoing.length || relations.incoming.length)">
              <EntityRelationMiniGraph
                :center-label="relations.entity_label"
                :outgoing="relations.outgoing"
                :incoming="relations.incoming"
                @focus-entity="focusEntityInTree"
              />
              <p class="mt-1 text-xs text-stone-500">{{ t('memory.tree.relationGraphHint') }}</p>
              <div class="mt-2 space-y-1 text-sm text-stone-300">
                <p
                  v-for="(edge, idx) in relations.outgoing"
                  :key="'o' + idx"
                >
                  {{
                    t('memory.tree.relationOutgoing', {
                      label: edge.peer_label,
                      predicate: edge.predicate,
                    })
                  }}
                </p>
                <p
                  v-for="(edge, idx) in relations.incoming"
                  :key="'i' + idx"
                >
                  {{
                    t('memory.tree.relationIncoming', {
                      label: edge.peer_label,
                      predicate: edge.predicate,
                    })
                  }}
                </p>
              </div>
            </template>
            <p
              v-else
              class="mt-2 text-xs text-stone-500"
            >
              {{ t('memory.tree.noRelations') }}
            </p>
          </div>
        </template>

        <template v-else-if="selectedKind === 'core_block'">
          <h3 class="text-base font-semibold text-stone-100">{{ t('memory.tree.coreBlock') }}</h3>
          <p class="mt-2 text-sm text-stone-400">{{ selectedTreeNode?.label }}</p>
          <button
            type="button"
            class="mt-4 rounded-xl bg-amber-600/90 px-4 py-2 text-sm font-medium text-stone-950 hover:bg-amber-500"
            @click="emit('open-personality')"
          >
            {{ t('memory.tree.openPersonalityBtn') }}
          </button>
        </template>

        <template v-else-if="selectedKind === 'archived' && selectedTreeNode">
          <h3 class="text-base font-semibold text-stone-100">{{ selectedTreeNode.label }}</h3>
          <p class="mt-3 text-sm text-stone-400">{{ t('memory.tree.archivedSource') }}</p>
          <p class="mt-2 font-mono text-xs text-stone-500">
            {{ String(selectedTreeNode.meta.source_id || '') }}
          </p>
        </template>

        <template v-else-if="selectedKind === 'compressed'">
          <p
            v-if="memoryLoading"
            class="text-sm text-stone-400"
          >
            {{ t('memory.loading') }}
          </p>
          <template v-else-if="memoryDetail">
            <MemoryCard
              :memory="memoryDetail"
              :expanded="true"
              show-pin
              show-delete
              @toggle-pin="togglePin"
              @delete="deleteMemory"
            />
            <div
              v-if="selectedTreeNode?.meta.compressed_from"
              class="mt-4"
            >
              <h4 class="text-xs font-medium uppercase tracking-wide text-stone-500">
                {{ t('memory.tree.compressedSources') }}
              </h4>
              <ul class="mt-2 space-y-1 text-xs font-mono text-stone-400">
                <li
                  v-for="sid in (selectedTreeNode.meta.compressed_from as string[])"
                  :key="sid"
                >
                  {{ sid }}
                </li>
              </ul>
            </div>
          </template>
        </template>

        <template v-else-if="selectedKind === 'memory'">
          <p
            v-if="memoryLoading"
            class="text-sm text-stone-400"
          >
            {{ t('memory.loading') }}
          </p>
          <MemoryCard
            v-else-if="memoryDetail"
            :memory="memoryDetail"
            :expanded="true"
            show-pin
            show-promote
            show-delete
            @toggle-pin="togglePin"
            @promote="promoteMemory"
            @delete="deleteMemory"
          />
        </template>
      </div>
    </div>
  </div>
</template>
