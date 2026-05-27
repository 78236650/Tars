---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Workspace Shell Dialog Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible desktop Inspector rail and unify the first batch of high-frequency dialogs and drawers under a shared Graphite Amber surface system.

**Architecture:** Keep Inspector state local to `DesktopShell` with desktop-only persistence, then introduce shared `AppSurfaceDialog` and `AppSurfaceDrawer` shell components that own layout, close affordances, scrolling, and footer treatment. Migrate high-frequency modal flows incrementally so each module keeps its current business logic while delegating chrome and interaction framing to the new shared surfaces.

**Tech Stack:** Vue 3, TypeScript, Vue Router, Pinia, Vite, Vitest, Vue Test Utils, Tailwind CSS

---

## File Map

- Modify: `frontend/src/components/layout/DesktopShell.vue`
- Modify: `frontend/src/components/layout/DesktopShell.spec.ts`
- Create: `frontend/src/components/common/AppSurfaceDialog.vue`
- Create: `frontend/src/components/common/AppSurfaceDrawer.vue`
- Create: `frontend/src/components/common/AppSurfaceDialog.spec.ts`
- Create: `frontend/src/components/common/AppSurfaceDrawer.spec.ts`
- Modify: `frontend/src/components/tools/ToolDetailModal.vue`
- Modify: `frontend/src/components/tools/AddToolModal.vue`
- Modify: `frontend/src/components/memory/MergePreviewDialog.vue`
- Modify: `frontend/src/components/memory/CompressDialog.vue`
- Modify: `frontend/src/components/memory/LongtermMemoryTab.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/components/bi/DataSourceSettings.vue`
- Modify: `frontend/src/components/settings/UserSettings.vue`
- Optional docs note if behavior changes materially: `docs/superpowers/specs/2026-05-16-workspace-shell-dialog-unification-design.md`

---

### Task 1: Add Desktop Inspector Collapse Rail

**Files:**
- Modify: `frontend/src/components/layout/DesktopShell.spec.ts`
- Modify: `frontend/src/components/layout/DesktopShell.vue`

- [ ] **Step 1: Write the failing desktop-collapse tests**

Add two tests to `frontend/src/components/layout/DesktopShell.spec.ts`:

```ts
it('renders a desktop collapse rail when the inspector is collapsed', async () => {
  localStorage.setItem('workspace.inspector.desktop', 'collapsed')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tools', component: { template: '<div />' }, meta: { desktopTitle: '工具', desktopSubtitle: '工具工作区' } }],
  })
  await router.push('/tools')
  await router.isReady()

  const wrapper = mount(DesktopShell, {
    global: {
      plugins: [router],
      stubs: {
        Sidebar: { template: '<div />' },
        ReminderBellButton: { template: '<button />' },
        ReminderNotificationsDrawer: { template: '<div />' },
      },
    },
    slots: { default: '<div />' },
  })

  expect(wrapper.find('[data-test="desktop-inspector-rail"]').exists()).toBe(true)
  expect(wrapper.text()).toContain('Tools')
})

it('expands the desktop inspector when the rail is clicked', async () => {
  localStorage.setItem('workspace.inspector.desktop', 'collapsed')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/memory', component: { template: '<div />' }, meta: { desktopTitle: '记忆', desktopSubtitle: '记忆工作区' } }],
  })
  await router.push('/memory')
  await router.isReady()

  const wrapper = mount(DesktopShell, {
    global: {
      plugins: [router],
      stubs: {
        Sidebar: { template: '<div />' },
        ReminderBellButton: { template: '<button />' },
        ReminderNotificationsDrawer: { template: '<div />' },
      },
    },
    slots: { default: '<div />' },
  })

  await wrapper.find('[data-test="desktop-inspector-rail"]').trigger('click')
  expect(wrapper.find('[data-test="desktop-inspector-panel"]').exists()).toBe(true)
  expect(localStorage.getItem('workspace.inspector.desktop')).toBe('expanded')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm run test:unit -- src/components/layout/DesktopShell.spec.ts
```

Expected: FAIL because `desktop-inspector-rail` and desktop collapse behavior do not exist yet.

- [ ] **Step 3: Implement desktop collapse state with persistence**

Update `frontend/src/components/layout/DesktopShell.vue` with a desktop-only persisted state:

```ts
import { computed, onMounted, ref, watch } from 'vue'

const DESKTOP_INSPECTOR_KEY = 'workspace.inspector.desktop'
const desktopInspectorState = ref<'expanded' | 'collapsed'>('expanded')

const isDesktopCollapsed = computed(() => desktopInspectorState.value === 'collapsed')

const setDesktopInspectorState = (next: 'expanded' | 'collapsed') => {
  desktopInspectorState.value = next
  window.localStorage.setItem(DESKTOP_INSPECTOR_KEY, next)
}

onMounted(() => {
  const saved = window.localStorage.getItem(DESKTOP_INSPECTOR_KEY)
  if (saved === 'collapsed' || saved === 'expanded') {
    desktopInspectorState.value = saved
  }
})
```

Extend the route context and template:

```ts
const shellContext = computed(() => {
  if (route.path.startsWith('/tools')) {
    return {
      title: 'Tool Control',
      shortLabel: 'Tools',
      description: '集中查看工具、技能和 SkillHub 安装入口。',
      items: [...],
      links: [...],
    }
  }
  if (route.path.startsWith('/memory')) {
    return {
      title: 'Memory Control',
      shortLabel: 'Memory',
      description: '围绕近期、长期、全部记忆与压缩动作快速切换。',
      items: [...],
      links: [...],
    }
  }
  return {
    title: 'Workspace Context',
    shortLabel: 'Shell',
    description: '当前页面关键状态、全局上下文与快速操作。',
    items: [...],
    links: [...],
  }
})
```

```vue
<div
  data-test="workspace-grid"
  class="grid min-w-0 grid-cols-[minmax(0,1fr)] xl:[grid-template-columns:minmax(0,1fr)_var(--inspector-width)]"
  :style="{ '--inspector-width': isDesktopCollapsed ? '48px' : '320px' }"
>
  <aside
    v-if="isDesktopCollapsed"
    data-test="desktop-inspector-rail"
    class="hidden xl:flex cursor-pointer flex-col items-center justify-between border-l border-amber-100/10 bg-[#110f0d]/96 py-5"
    @click="setDesktopInspectorState('expanded')"
  >
    <span class="rotate-180 [writing-mode:vertical-rl] text-[11px] uppercase tracking-[0.24em] text-stone-400">
      Inspector
    </span>
    <span class="text-xs text-amber-200">{{ shellContext.shortLabel }}</span>
  </aside>

  <aside
    v-else
    data-test="desktop-inspector-panel"
    class="hidden xl:flex h-full flex-col border-l border-amber-100/10 bg-[#110f0d]/96 px-5 py-5"
  >
    <button
      data-test="desktop-inspector-collapse"
      type="button"
      class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-xs text-stone-200"
      @click="setDesktopInspectorState('collapsed')"
    >
      收起
    </button>
    <!-- existing inspector content -->
  </aside>
</div>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
npm run test:unit -- src/components/layout/DesktopShell.spec.ts
```

Expected: PASS with all existing Inspector tests and the two new desktop-collapse tests passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/DesktopShell.vue frontend/src/components/layout/DesktopShell.spec.ts
git commit -m "feat: add collapsible desktop inspector rail"
```

### Task 2: Build Shared Dialog and Drawer Surfaces

**Files:**
- Create: `frontend/src/components/common/AppSurfaceDialog.vue`
- Create: `frontend/src/components/common/AppSurfaceDrawer.vue`
- Create: `frontend/src/components/common/AppSurfaceDialog.spec.ts`
- Create: `frontend/src/components/common/AppSurfaceDrawer.spec.ts`

- [ ] **Step 1: Write the failing shared-surface tests**

Create `frontend/src/components/common/AppSurfaceDialog.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppSurfaceDialog from './AppSurfaceDialog.vue'

describe('AppSurfaceDialog', () => {
  it('renders title, description, and footer slot', () => {
    const wrapper = mount(AppSurfaceDialog, {
      props: { open: true, title: '编辑技能', description: '统一弹层壳' },
      slots: {
        default: '<div class="body">Body</div>',
        footer: '<button class="save">保存</button>',
      },
    })

    expect(wrapper.text()).toContain('编辑技能')
    expect(wrapper.text()).toContain('统一弹层壳')
    expect(wrapper.find('.save').exists()).toBe(true)
  })

  it('emits close when the close button is clicked', async () => {
    const wrapper = mount(AppSurfaceDialog, {
      props: { open: true, title: '编辑技能' },
    })

    await wrapper.find('[data-test="surface-close"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
```

Create `frontend/src/components/common/AppSurfaceDrawer.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppSurfaceDrawer from './AppSurfaceDrawer.vue'

describe('AppSurfaceDrawer', () => {
  it('renders right-side drawer content when open', () => {
    const wrapper = mount(AppSurfaceDrawer, {
      props: { open: true, title: '提醒详情', side: 'right' },
      slots: { default: '<div class="drawer-body">Drawer</div>' },
    })

    expect(wrapper.find('.drawer-body').exists()).toBe(true)
    expect(wrapper.text()).toContain('提醒详情')
  })
})
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
npm run test:unit -- src/components/common/AppSurfaceDialog.spec.ts src/components/common/AppSurfaceDrawer.spec.ts
```

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement the shared surface components**

Create `frontend/src/components/common/AppSurfaceDialog.vue`:

```vue
<script setup lang="ts">
const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
}>(), {
  description: '',
  size: 'lg',
})

const emit = defineEmits<{ close: [] }>()

const widthClass = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
  xl: 'max-w-5xl',
}[props.size]
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <button class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="emit('close')" />
    <section :class="['relative w-full overflow-hidden rounded-[28px] border border-amber-100/10 bg-[#171411] shadow-[0_30px_100px_rgba(8,7,5,0.65)]', widthClass]">
      <header class="flex items-start justify-between border-b border-amber-100/10 px-6 py-5">
        <div>
          <h2 class="text-xl font-semibold text-stone-100">{{ title }}</h2>
          <p v-if="description" class="mt-1 text-sm text-stone-400">{{ description }}</p>
        </div>
        <button data-test="surface-close" class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-200" @click="emit('close')">
          关闭
        </button>
      </header>
      <div class="max-h-[70vh] overflow-y-auto px-6 py-5">
        <slot />
      </div>
      <footer v-if="$slots.footer" class="border-t border-amber-100/10 px-6 py-4">
        <slot name="footer" />
      </footer>
    </section>
  </div>
</template>
```

Create `frontend/src/components/common/AppSurfaceDrawer.vue`:

```vue
<script setup lang="ts">
const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  side?: 'left' | 'right'
}>(), {
  description: '',
  side: 'right',
})

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50">
    <button class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="emit('close')" />
    <aside
      :class="[
        'absolute inset-y-0 w-full max-w-xl border-l border-amber-100/10 bg-[#171411] shadow-[0_30px_100px_rgba(8,7,5,0.65)]',
        side === 'right' ? 'right-0' : 'left-0 border-r border-l-0',
      ]"
    >
      <header class="flex items-start justify-between border-b border-amber-100/10 px-6 py-5">
        <div>
          <h2 class="text-xl font-semibold text-stone-100">{{ title }}</h2>
          <p v-if="description" class="mt-1 text-sm text-stone-400">{{ description }}</p>
        </div>
        <button data-test="surface-close" class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-200" @click="emit('close')">
          关闭
        </button>
      </header>
      <div class="h-[calc(100%-80px)] overflow-y-auto px-6 py-5">
        <slot />
      </div>
      <footer v-if="$slots.footer" class="border-t border-amber-100/10 px-6 py-4">
        <slot name="footer" />
      </footer>
    </aside>
  </div>
</template>
```

- [ ] **Step 4: Run the shared-surface tests**

Run:

```bash
npm run test:unit -- src/components/common/AppSurfaceDialog.spec.ts src/components/common/AppSurfaceDrawer.spec.ts
```

Expected: PASS with both shared surface specs green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/common/AppSurfaceDialog.vue frontend/src/components/common/AppSurfaceDrawer.vue frontend/src/components/common/AppSurfaceDialog.spec.ts frontend/src/components/common/AppSurfaceDrawer.spec.ts
git commit -m "feat: add shared dialog and drawer surfaces"
```

### Task 3: Migrate Tool Modals to Shared Dialog Surface

**Files:**
- Modify: `frontend/src/components/tools/ToolDetailModal.vue`
- Modify: `frontend/src/components/tools/AddToolModal.vue`
- Test: `frontend/src/components/common/AppSurfaceDialog.spec.ts`

- [ ] **Step 1: Write a failing tool-modal integration test**

Extend `frontend/src/components/common/AppSurfaceDialog.spec.ts` with a snapshot-style integration assertion:

```ts
it('supports tool-style footer actions and scrolling content', () => {
  const wrapper = mount(AppSurfaceDialog, {
    props: { open: true, title: '添加技能', description: '创建新的 Prompt Skill', size: 'xl' },
    slots: {
      default: '<div class="long-content" style="height: 1200px">Long body</div>',
      footer: '<div class="actions"><button>取消</button><button>创建</button></div>',
    },
  })

  expect(wrapper.find('.long-content').exists()).toBe(true)
  expect(wrapper.text()).toContain('创建')
})
```

- [ ] **Step 2: Run the test to verify the current tool modals still use custom shells**

Run:

```bash
npm run test:unit -- src/components/common/AppSurfaceDialog.spec.ts
```

Expected: PASS for the shared shell but `ToolDetailModal.vue` and `AddToolModal.vue` still contain inline modal chrome in review.

- [ ] **Step 3: Replace custom tool modal chrome with `AppSurfaceDialog`**

Update `frontend/src/components/tools/AddToolModal.vue`:

```vue
<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
// existing form logic stays
</script>

<template>
  <AppSurfaceDialog
    :open="true"
    :title="t('addSkill.title')"
    description="创建新的 Prompt Skill"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <!-- existing form fields -->
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200" @click="emit('close')">
          {{ t('common.cancel') }}
        </button>
        <button class="rounded-2xl bg-amber-500 px-4 py-2 font-medium text-stone-950" @click="submit">
          {{ t('common.create') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
```

Update `frontend/src/components/tools/ToolDetailModal.vue` with the same shell:

```vue
<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
// existing logic stays
</script>

<template>
  <AppSurfaceDialog
    :open="true"
    :title="props.tool.name"
    :description="props.tool.description"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <!-- existing metadata, config, usage -->
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200" @click="emit('close')">
          {{ t('common.close') }}
        </button>
        <button class="rounded-2xl bg-amber-500 px-4 py-2 font-medium text-stone-950" @click="toggleEnabled">
          {{ isEnabled ? t('toolDetail.disable') : t('toolDetail.enable') }}
        </button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
```

- [ ] **Step 4: Run focused tests and a build**

Run:

```bash
npm run test:unit -- src/components/common/AppSurfaceDialog.spec.ts
npm run build
```

Expected: PASS, and the app still builds after the tool modal migration.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tools/ToolDetailModal.vue frontend/src/components/tools/AddToolModal.vue frontend/src/components/common/AppSurfaceDialog.vue frontend/src/components/common/AppSurfaceDialog.spec.ts
git commit -m "refactor: move tool modals onto shared dialog surface"
```

### Task 4: Migrate Memory Dialog Flows

**Files:**
- Modify: `frontend/src/components/memory/MergePreviewDialog.vue`
- Modify: `frontend/src/components/memory/CompressDialog.vue`
- Modify: `frontend/src/components/memory/LongtermMemoryTab.vue`

- [ ] **Step 1: Write the failing memory dialog test**

Add a targeted assertion to the memory dialog spec you create or extend with `LongtermMemoryTab` mounting:

```ts
it('opens merge preview inside the shared dialog shell', async () => {
  const wrapper = mount(MergePreviewDialog, {
    props: {
      open: true,
      loading: false,
      preview: {
        merged_content: '压缩后的摘要',
        source_count: 2,
        importance: 0.8,
        category: 'fact',
        entity_refs: ['TARS'],
      },
    },
  })

  expect(wrapper.text()).toContain('压缩后的摘要')
  expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm run test:unit -- src/components/memory/MergePreviewDialog.spec.ts
```

Expected: FAIL because the spec file and shared close affordance do not exist yet.

- [ ] **Step 3: Replace memory dialog chrome with `AppSurfaceDialog`**

Update `frontend/src/components/memory/MergePreviewDialog.vue`:

```vue
<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
</script>

<template>
  <AppSurfaceDialog
    :open="open"
    title="合并预览"
    description="确认长期记忆合并后的内容与元数据"
    size="xl"
    @close="$emit('close')"
  >
    <div class="space-y-4">
      <!-- existing preview body -->
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200" @click="$emit('close')">取消</button>
        <button class="rounded-2xl bg-amber-500 px-4 py-2 font-medium text-stone-950" @click="$emit('confirm')">确认合并</button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
```

Update `frontend/src/components/memory/CompressDialog.vue` and any inline edit panel in `LongtermMemoryTab.vue` with the same shell and button system.

- [ ] **Step 4: Run the focused tests and a build**

Run:

```bash
npm run test:unit -- src/components/memory/MergePreviewDialog.spec.ts
npm run build
```

Expected: PASS with the merge preview shell assertion green and the app building successfully.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/memory/MergePreviewDialog.vue frontend/src/components/memory/CompressDialog.vue frontend/src/components/memory/LongtermMemoryTab.vue frontend/src/components/memory/MergePreviewDialog.spec.ts
git commit -m "refactor: unify memory dialogs with shared surface"
```

### Task 5: Migrate Knowledge, BI, and Settings Core Dialogs

**Files:**
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/components/bi/DataSourceSettings.vue`
- Modify: `frontend/src/components/settings/UserSettings.vue`
- Test: existing or new focused specs adjacent to the touched components

- [ ] **Step 1: Add a single failing smoke test for one migrated module**

Create a shared smoke spec such as `frontend/src/components/settings/UserSettings.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import UserSettings from './UserSettings.vue'

describe('UserSettings', () => {
  it('uses shared surface classes for modal content', () => {
    const wrapper = mount(UserSettings)
    expect(wrapper.html()).toContain('rounded-[28px]')
  })
})
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run:

```bash
npm run test:unit -- src/components/settings/UserSettings.spec.ts
```

Expected: FAIL because the current settings modal still uses its own shell or no shared-surface class names.

- [ ] **Step 3: Migrate each module onto the shared surface layer**

Apply the same pattern in each file:

```vue
<script setup lang="ts">
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import AppSurfaceDrawer from '@/components/common/AppSurfaceDrawer.vue'
</script>
```

Use `AppSurfaceDialog` for centered form/config flows:

```vue
<AppSurfaceDialog
  :open="showConfig"
  title="数据源设置"
  description="统一配置 BI 数据源连接信息"
  size="lg"
  @close="showConfig = false"
>
  <div class="space-y-4">
    <!-- existing form -->
  </div>
</AppSurfaceDialog>
```

Use `AppSurfaceDrawer` for longer detail flows where the existing content already behaves like a side panel:

```vue
<AppSurfaceDrawer
  :open="showDetail"
  title="知识条目详情"
  description="查看文档状态与操作记录"
  side="right"
  @close="showDetail = false"
>
  <div class="space-y-4">
    <!-- existing detail body -->
  </div>
</AppSurfaceDrawer>
```

- [ ] **Step 4: Run focused tests and the app build**

Run:

```bash
npm run test:unit -- src/components/settings/UserSettings.spec.ts
npm run build
```

Expected: PASS with the smoke assertion green and the app build intact.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge/KnowledgeManager.vue frontend/src/components/bi/DataSourceSettings.vue frontend/src/components/settings/UserSettings.vue frontend/src/components/settings/UserSettings.spec.ts
git commit -m "refactor: unify core workspace dialogs"
```

### Task 6: Regression Sweep and Preview Verification

**Files:**
- Modify if needed: any of the files above after diagnostics

- [ ] **Step 1: Run diagnostics on recently changed Vue files**

Check diagnostics for:

```text
frontend/src/components/layout/DesktopShell.vue
frontend/src/components/common/AppSurfaceDialog.vue
frontend/src/components/common/AppSurfaceDrawer.vue
frontend/src/components/tools/ToolDetailModal.vue
frontend/src/components/tools/AddToolModal.vue
frontend/src/components/memory/MergePreviewDialog.vue
frontend/src/components/memory/CompressDialog.vue
frontend/src/components/memory/LongtermMemoryTab.vue
frontend/src/components/knowledge/KnowledgeManager.vue
frontend/src/components/bi/DataSourceSettings.vue
frontend/src/components/settings/UserSettings.vue
```

Expected: no new linter or type errors.

- [ ] **Step 2: Run the targeted unit suite**

Run:

```bash
npm run test:unit -- \
  src/components/layout/DesktopShell.spec.ts \
  src/components/common/AppSurfaceDialog.spec.ts \
  src/components/common/AppSurfaceDrawer.spec.ts \
  src/components/memory/MergePreviewDialog.spec.ts \
  src/components/settings/UserSettings.spec.ts
```

Expected: PASS for all focused shell and dialog coverage.

- [ ] **Step 3: Run the production build**

Run:

```bash
npm run build
```

Expected: PASS with only pre-existing chunk-size warnings allowed.

- [ ] **Step 4: Start preview and manually verify the core flows**

Run:

```bash
npm run dev -- --host 127.0.0.1 --port 4175
```

Manually verify:

```text
1. DesktopShell on /tools: expand -> collapse -> expand
2. DesktopShell on /memory: collapse persists after route switch
3. Tools: open tool detail, open add skill, confirm footer/button consistency
4. Memory: open merge preview and compression dialog
5. Knowledge / BI / Settings: open one core dialog each and confirm shell consistency
```

Expected: the desktop rail remains clickable, mobile drawer still opens, and the first-batch dialogs all share the same Graphite Amber shell language.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/DesktopShell.vue frontend/src/components/layout/DesktopShell.spec.ts frontend/src/components/common/AppSurfaceDialog.vue frontend/src/components/common/AppSurfaceDrawer.vue frontend/src/components/common/AppSurfaceDialog.spec.ts frontend/src/components/common/AppSurfaceDrawer.spec.ts frontend/src/components/tools/ToolDetailModal.vue frontend/src/components/tools/AddToolModal.vue frontend/src/components/memory/MergePreviewDialog.vue frontend/src/components/memory/CompressDialog.vue frontend/src/components/memory/LongtermMemoryTab.vue frontend/src/components/knowledge/KnowledgeManager.vue frontend/src/components/bi/DataSourceSettings.vue frontend/src/components/settings/UserSettings.vue
git commit -m "feat: unify workspace inspector and core dialog surfaces"
```

---

## Self-Review

- **Spec coverage:** Covered desktop Inspector collapse, persistence, shared dialog/drawer surfaces, first-batch modal migrations, focused tests, and manual verification.
- **Placeholder scan:** Removed `TODO`-style language and replaced it with explicit files, commands, and concrete shell snippets.
- **Type consistency:** Reused the same component names and Inspector state names throughout: `AppSurfaceDialog`, `AppSurfaceDrawer`, `expanded`, `collapsed`, `mobile-open`, and `shortLabel`.
