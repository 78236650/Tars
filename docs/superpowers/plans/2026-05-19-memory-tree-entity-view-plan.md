# 记忆实体树 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/memory` 新增「实体」Tab，用实体树鸟瞰当前租户记忆，选中实体后展示关系短列表与记忆详情；保留现有列表 Tab 不变。

**Architecture:** 后端 `EntityTreeBuilder` 单次查询 memories + 内存分组 → `GET /api/memory/tree` 返回嵌套 nodes；前端左树右详情，叶子操作复用 `MemoryCard`。关系走 `GET /api/memory/tree/relations` 按需加载。不做首屏力导向图。

**Tech Stack:** Python 3.11+, FastAPI, Vue 3 + TypeScript, SQLite, 现有 Tailwind 手写 UI

**规格:** [`docs/superpowers/specs/2026-05-19-memory-tree-entity-view-design.md`](../specs/2026-05-19-memory-tree-entity-view-design.md)

**预计工期:** Phase 1 约 5 工作日；Phase 2 约 3 工作日

---

## 文件结构

```
backend/tars/memory/
├── tree_builder.py              # [NEW] EntityTreeBuilder + normalize_entity_ref
└── (existing core_memory, compressor)

backend/tars/api/
└── memory.py                    # [EXTEND] /tree, /tree/relations, /tree/search

backend/tests/
└── test_memory_tree_api.py      # [NEW]

frontend/src/
├── views/MemoryView.vue         # [EXTEND] tab tree
├── api/index.ts                 # [EXTEND] memoryApi.getTree, getTreeRelations, searchTree
├── types/index.ts               # [EXTEND] TreeNode, MemoryTreeResponse
├── i18n/index.ts                # [EXTEND] memory.tab.entity, memory.tree.*
└── components/memory/
    ├── MemoryTreeTab.vue        # [NEW]
    ├── MemoryTreePanel.vue      # [NEW] 左树
    └── MemoryEntityDetail.vue   # [NEW] 右详情+关系
```

---

## Phase 1 — MVP（可独立上线）

### Task 1: 实体引用规范化工具

**Files:**
- Create: `backend/tars/memory/tree_builder.py`
- Test: `backend/tests/test_memory_tree_api.py`

- [ ] **Step 1: 写失败测试 `normalize_entity_ref`**

```python
def test_normalize_entity_ref_string_id():
    assert normalize_entity_ref("person:a1b2c3d4") == ("person:a1b2c3d4", "person", "a1b2c3d4")

def test_normalize_entity_ref_dict():
    ref = {"name": "Alice", "type": "person"}
    eid, etype, _ = normalize_entity_ref(ref)
    assert etype == "person"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/test_memory_tree_api.py::test_normalize_entity_ref_string_id -v`

- [ ] **Step 3: 实现 `normalize_entity_ref` + `primary_entity_id(memory)`**

- [ ] **Step 4: 测试通过**

---

### Task 2: EntityTreeBuilder 核心

**Files:**
- Modify: `backend/tars/memory/tree_builder.py`
- Modify: `backend/tars/database/base.py`（可选：新增 `list_memories_for_tree(tenant_id, limit=5000)`）
- Test: `backend/tests/test_memory_tree_api.py`

- [ ] **Step 1: 写失败测试 — 空租户返回 `__core__` + 空态 stats**

- [ ] **Step 2: 实现 `build(tenant_id, max_per_bucket=30)`**

  - 分支：`__core__`（调 `CoreMemoryManager.get_all()`）
  - 按 `entity_refs[0]` 分组 → `__type:{type}` → entity 节点
  - 每桶：`longterm` / `recent`(7d) / `compressed`
  - `__orphan__`：无 refs 记忆
  - `stats`: entity_count, orphan_count, ghost_entity_count

- [ ] **Step 3: 写测试 — 两实体、共现记忆只在主实体下**

- [ ] **Step 4: 写测试 — 桶截断 `truncated: true`**

- [ ] **Step 5: pytest 全绿**

Run: `cd backend && pytest tests/test_memory_tree_api.py -v`

---

### Task 3: Memory Tree API

**Files:**
- Modify: `backend/tars/api/memory.py`

- [ ] **Step 1: 写失败测试 `GET /api/memory/tree` 返回 200 + nodes**

- [ ] **Step 2: 注册路由**

```python
@router.get("/tree")
def get_memory_tree(...):
    builder = EntityTreeBuilder(_require_db(), tenant_id=tenant_id)
    return builder.build(...)
```

- [ ] **Step 3: 写失败测试 `GET /api/memory/tree/relations?entity_id=`**

- [ ] **Step 4: 实现 relations 端点（查 `relations` 表 + 解析 to/from label）**

- [ ] **Step 5: Admin `user_id` 非 admin 403 测试**

- [ ] **Step 6: pytest 通过**

---

### Task 4: 前端类型与 API

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: 定义 `MemoryTreeNode`, `MemoryTreeResponse`, `EntityRelationsResponse`**

- [ ] **Step 2: 添加 `memoryApi.getTree`, `getTreeRelations`**

- [ ] **Step 3: `npm run build` 类型检查通过**（在 frontend 目录）

---

### Task 5: MemoryTreeTab UI

**Files:**
- Create: `frontend/src/components/memory/MemoryTreeTab.vue`
- Create: `frontend/src/components/memory/MemoryTreePanel.vue`
- Create: `frontend/src/components/memory/MemoryEntityDetail.vue`
- Modify: `frontend/src/views/MemoryView.vue`
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: `MemoryView` tabs 增加 `{ key: 'tree', label: t('memory.tab.entity') }`（放在 longterm 与 all 之间）**

- [ ] **Step 2: `MemoryTreeTab` 挂载，onMounted 调 `getTree`**

- [ ] **Step 3: 左树递归组件 — 展开/折叠，实体节点显示 `(memory_count)`**

- [ ] **Step 4: 点击 `kind=entity` → 加载 relations + 显示实体摘要**

- [ ] **Step 5: 点击 `kind=memory` → 右侧 `MemoryCard` 或复用现有卡片逻辑**

- [ ] **Step 6: 空态、loading、error 态**

- [ ] **Step 7: 刷新按钮触发父组件 `loadStats`**

---

### Task 6: Phase 1 验收

- [ ] **手动验收清单**

  1. 打开 `/memory` →「实体」Tab 可见
  2. 有记忆的租户：看到人物/项目等分组
  3. 展开实体 → 长期/近期/压缩桶 → 点开叶子见详情
  4. 选中实体 → 右侧关系区（无关系时空态）
  5. 近期/长期/全部 Tab 行为未变

- [ ] **回归测试**

Run: `cd backend && pytest tests/test_memory_tree_api.py tests/test_memory_management_api.py -v`

---

## Phase 2 — 增强（可选紧随 Phase 1）

### Task 7: 树内搜索

**Files:**
- Modify: `backend/tars/memory/tree_builder.py`
- Modify: `backend/tars/api/memory.py`
- Modify: `frontend/src/components/memory/MemoryTreeTab.vue`

- [x] **Step 1: `GET /api/memory/tree/search?q=&limit=20` 返回 path + label**

- [x] **Step 2: 前端搜索框防抖，自动 `expandPath`**

---

### Task 8: Admin 用户联动

**Files:**
- Modify: `frontend/src/views/MemoryView.vue`
- Modify: `frontend/src/components/memory/MemoryTreeTab.vue`

- [x] **Step 1: Admin 在管理 Tab 选中用户后，实体 Tab 可带 `user_id` 拉树**

- [x] **Step 2: 顶栏显示「正在查看: {user}」**

---

### Task 9: 跳转长期记忆 Tab

**Files:**
- Modify: `frontend/src/components/memory/LongtermMemoryTab.vue`
- Modify: `frontend/src/views/MemoryView.vue`

- [x] **Step 1: 按钮「在长期记忆中管理」→ `activeTab=longterm` + 传递 entity 筛选**

---

## Phase 3 — 已完成（2026-05-19）

- [x] `view=provenance` 压缩谱系子视图（Tab 内 Segmented：实体 | 谱系）
- [x] 大树默认折叠策略（可展开节点 >120 时仅展开顶层 + 提示）
- [x] 关系迷你图（轻量 SVG，点击跳转实体）— 替代满屏力导向图
- [x] 大树折叠策略 + `tree_node_count` 统计（替代完整虚拟滚动）
- [ ] 满屏力导向图谱（明确延后 v4.2+）

---

## Commit 建议

| Commit | 内容 |
|--------|------|
| 1 | `feat(memory): add EntityTreeBuilder and unit tests` |
| 2 | `feat(memory): add GET /api/memory/tree and relations` |
| 3 | `feat(frontend): add 实体 tab with memory tree UI` |
| 4 | `feat(memory): tree search and admin user scope`（Phase 2） |

---

## 不在本计划内

- 修改 Reflector 写入逻辑
- `entities` 表 CRUD UI
- 记忆导出格式变更
- 力导向图组件引入
