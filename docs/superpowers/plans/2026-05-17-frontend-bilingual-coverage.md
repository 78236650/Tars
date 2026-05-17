# Frontend Bilingual Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every primary frontend page switch cleanly between Chinese and English, including desktop header copy, page content, dialogs, toasts, confirms, and frontend-generated status text.

**Architecture:** Keep the current lightweight `frontend/src/i18n/index.ts` approach, but turn it into the single source of truth for all user-facing frontend copy. Route meta will carry i18n keys instead of hard-coded Chinese text, `DesktopShell` will translate those keys reactively, and each page/component will be migrated in groups so tests and manual verification can stay focused.

**Tech Stack:** Vue 3, TypeScript, Vue Router, Pinia, Vite, Vitest, Vue Test Utils, Tailwind CSS

---

## File Map

- Modify: `frontend/src/i18n/index.ts`
- Create: `frontend/src/i18n/index.spec.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/DesktopShell.vue`
- Modify: `frontend/src/components/layout/DesktopShell.spec.ts`
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/views/ModelsView.vue`
- Modify: `frontend/src/views/ToolsView.vue`
- Modify: `frontend/src/views/MeetingView.vue`
- Modify: `frontend/src/views/BiAnalyticsView.vue`
- Modify: `frontend/src/views/MemoryView.vue`
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/components/layout/Sidebar.vue`
- Modify: `frontend/src/components/settings/SubAgentSettings.vue`
- Modify: `frontend/src/components/settings/UserSettings.vue`
- Modify: `frontend/src/components/settings/PersonalitySettings.vue`
- Modify: `frontend/src/components/meeting/AudioUploader.vue`
- Modify: `frontend/src/components/meeting/MeetingSettings.vue`
- Modify: `frontend/src/components/meeting/RecordingPanel.vue`
- Modify: `frontend/src/components/meeting/TranscriptionList.vue`
- Modify: `frontend/src/components/meeting/TranscriptionDetail.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/components/knowledge/DocumentUploader.vue`
- Modify: `frontend/src/components/bi/DataSourceSettings.vue`
- Modify: `frontend/src/components/bi/SchemaAnnotator.vue`
- Modify: `frontend/src/components/memory/RecentMemoryTab.vue`
- Modify: `frontend/src/components/memory/LongtermMemoryTab.vue`
- Modify: `frontend/src/components/memory/AllMemoryTab.vue`
- Modify: `frontend/src/components/memory/MemoryCard.vue`
- Modify: `frontend/src/components/memory/CompressDialog.vue`
- Modify: `frontend/src/components/memory/MergePreviewDialog.vue`
- Modify: `frontend/src/components/chat/ChatPanel.vue`
- Modify: `frontend/src/components/chat/ReminderBellButton.vue`
- Modify: `frontend/src/components/chat/ReminderNotificationsDrawer.vue`
- Modify: `frontend/src/components/chat/PlanCard.vue`
- Modify: `frontend/src/components/chat/TaskCard.vue`
- Optional verification-only touches: `frontend/src/components/tools/ToolCard.vue`, `frontend/src/components/tools/ToolDetailModal.vue`, `frontend/src/components/tools/AddToolModal.vue`
- Docs reference only: `docs/superpowers/specs/2026-05-17-frontend-bilingual-coverage-design.md`

---

### Task 1: Stabilize the i18n Core and Add Test Coverage

**Files:**
- Create: `frontend/src/i18n/index.spec.ts`
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: Write the failing i18n helper tests**

Create `frontend/src/i18n/index.spec.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest'
import { useI18n } from './index'

describe('useI18n', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('toggles locale and persists the selected language', () => {
    const { locale, toggleLocale } = useI18n()

    expect(locale.value).toBe('zh')

    toggleLocale()

    expect(locale.value).toBe('en')
    expect(localStorage.getItem('tars_locale')).toBe('en')
  })

  it('falls back to zh and supports parameter replacement', () => {
    const { t, setLocale } = useI18n()

    setLocale('en')

    expect(t('common.save')).toBe('Save')
    expect(t('missing.key')).toBe('missing.key')
    expect(t('modelsPage.fetchOk', { count: 3 })).toBe('Fetched 3 models')
  })
})
```

- [ ] **Step 2: Run the i18n test to verify it fails**

Run:

```bash
npm run test:unit -- src/i18n/index.spec.ts
```

Expected: FAIL because `t()` does not yet accept params and `modelsPage.fetchOk` does not exist.

- [ ] **Step 3: Extend the helper and baseline dictionaries**

Update `frontend/src/i18n/index.ts`:

```ts
type MessageParams = Record<string, string | number>

const interpolate = (template: string, params?: MessageParams): string => {
  if (!params) return template
  return Object.entries(params).reduce((acc, [key, value]) => {
    return acc.replaceAll(`{${key}}`, String(value))
  }, template)
}

const t = (key: string, params?: MessageParams): string => {
  const raw = messages[locale.value]?.[key] || messages.zh[key] || key
  return interpolate(raw, params)
}
```

Add missing base keys that will be reused across later tasks:

```ts
'common.model': 'Model',
'common.notSelected': 'Not selected',
'common.backToChat': 'Back to Chat',
'common.deleteFailed': 'Delete failed',
'desktop.default.title': 'TARS Workspace',
'desktop.default.subtitle': 'Unified workspace shell',
'modelsPage.fetchOk': 'Fetched {count} models',
```

Chinese entries:

```ts
'common.model': '模型',
'common.notSelected': '未选择',
'common.backToChat': '返回聊天',
'common.deleteFailed': '删除失败',
'desktop.default.title': 'TARS 工作台',
'desktop.default.subtitle': '统一桌面工作台',
'modelsPage.fetchOk': '已拉取 {count} 个模型',
```

- [ ] **Step 4: Run the i18n tests to verify they pass**

Run:

```bash
npm run test:unit -- src/i18n/index.spec.ts
```

Expected: PASS with locale persistence, fallback, and parameter interpolation all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/i18n/index.ts frontend/src/i18n/index.spec.ts
git commit -m "feat: strengthen i18n helper for bilingual coverage"
```

### Task 2: Move Desktop Header Copy to Route Keys

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/DesktopShell.vue`
- Modify: `frontend/src/components/layout/DesktopShell.spec.ts`

- [ ] **Step 1: Write the failing desktop-shell route-key test**

Extend `frontend/src/components/layout/DesktopShell.spec.ts`:

```ts
it('renders desktop title and subtitle from i18n route keys', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/models',
        component: { template: '<div />' },
        meta: {
          desktopTitleKey: 'desktop.models.title',
          desktopSubtitleKey: 'desktop.models.subtitle',
        },
      },
    ],
  })

  await router.push('/models')
  await router.isReady()

  const wrapper = mount(DesktopShell, {
    global: {
      plugins: [router],
      stubs: {
        LeftPanel: { template: '<div />' },
        RightPanel: { template: '<div />' },
        ReminderBellButton: { template: '<button />' },
        ReminderNotificationsDrawer: { template: '<div />' },
      },
    },
    slots: { default: '<div />' },
  })

  expect(wrapper.text()).toContain('模型中心')

  const { setLocale } = useI18n()
  setLocale('en')
  await nextTick()

  expect(wrapper.text()).toContain('Model Center')
})
```

- [ ] **Step 2: Run the desktop-shell spec to verify it fails**

Run:

```bash
npm run test:unit -- src/components/layout/DesktopShell.spec.ts
```

Expected: FAIL because the shell still reads plain `desktopTitle` and `desktopSubtitle`.

- [ ] **Step 3: Switch router meta and shell rendering to keys**

Update route meta in `frontend/src/router/index.ts`:

```ts
meta: {
  desktopTitleKey: 'desktop.models.title',
  desktopSubtitleKey: 'desktop.models.subtitle',
}
```

Update `frontend/src/components/layout/DesktopShell.vue`:

```ts
import { computed } from 'vue'
import { useI18n } from '@/i18n'

const { t } = useI18n()

const desktopTitle = computed(() =>
  t(String(route.meta.desktopTitleKey || 'desktop.default.title'))
)

const desktopSubtitle = computed(() =>
  t(String(route.meta.desktopSubtitleKey || 'desktop.default.subtitle'))
)
```

Replace remaining header hard-coded copy:

```vue
<div class="text-[11px] uppercase tracking-[0.22em] text-stone-500">{{ t('common.model') }}</div>
<div class="mt-1 text-sm font-medium text-stone-100">{{ settingsStore.currentModel || t('common.notSelected') }}</div>
<button ...>{{ t('nav.models') }}</button>
```

Add the corresponding `desktop.*` keys for each route to `frontend/src/i18n/index.ts`.

- [ ] **Step 4: Run the desktop-shell spec to verify it passes**

Run:

```bash
npm run test:unit -- src/components/layout/DesktopShell.spec.ts
```

Expected: PASS with the route-key test and existing shell tests all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/layout/DesktopShell.vue frontend/src/components/layout/DesktopShell.spec.ts frontend/src/i18n/index.ts
git commit -m "feat: localize desktop shell route headers"
```

### Task 3: Complete Settings, Models, and Tools Page-Level Localization

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/views/ModelsView.vue`
- Modify: `frontend/src/views/ToolsView.vue`
- Modify: `frontend/src/components/settings/SubAgentSettings.vue`
- Modify: `frontend/src/components/settings/UserSettings.vue`
- Modify: `frontend/src/components/settings/PersonalitySettings.vue`
- Optional verify-only: `frontend/src/components/tools/ToolDetailModal.vue`
- Optional verify-only: `frontend/src/components/tools/AddToolModal.vue`

- [ ] **Step 1: Write a failing representative page test**

Add a test to `frontend/src/components/layout/DesktopShell.spec.ts` or create `frontend/src/views/SettingsView.spec.ts`:

```ts
it('switches settings page header and back button copy with locale', async () => {
  const wrapper = mount(SettingsView, {
    global: {
      stubs: { RouterView: { template: '<div />' } },
    },
  })

  expect(wrapper.text()).toContain('设置')
  expect(wrapper.text()).toContain('返回聊天')

  const { setLocale } = useI18n()
  setLocale('en')
  await nextTick()

  expect(wrapper.text()).toContain('Settings')
  expect(wrapper.text()).toContain('Back to Chat')
})
```

- [ ] **Step 2: Run the focused spec to verify it fails**

Run:

```bash
npm run test:unit -- src/views/SettingsView.spec.ts
```

Expected: FAIL because `SettingsView.vue` still contains hard-coded `Workspace`, `Settings`, and `t('back to chat')`.

- [ ] **Step 3: Replace hard-coded copy in the settings/models/tools group**

Update `frontend/src/views/SettingsView.vue`:

```vue
<div class="text-[11px] uppercase tracking-[0.24em] text-stone-500">{{ t('desktop.settings.eyebrow') }}</div>
<h1 class="mt-2 text-xl font-semibold text-stone-100">{{ t('settings.title') }}</h1>
<button ...>{{ t('common.backToChat') }}</button>
```

Update `frontend/src/views/ModelsView.vue` to replace any direct string concatenation:

```ts
toast.success(t('modelsPage.fetchOk', { count: r.models.length }))
toast.success(t('modelsPage.fetchEmpty'))
toast.error(t('sidebar.switchFailed'))
```

Update `frontend/src/views/ToolsView.vue` to localize any remaining hard-coded labels:

```vue
{{ skill.type === 'plugin' ? t('tools.pluginType') : t('tools.promptType') }}
{{ pkg.type === 'plugin' ? t('tools.marketToolType') : t('tools.marketPromptType') }}
```

Add or fix missing keys in `frontend/src/i18n/index.ts` for:

```text
desktop.settings.eyebrow
tools.pluginType
tools.promptType
tools.marketToolType
tools.marketPromptType
settings.tabs.subagents
settings.tabs.users
settings.tabs.personality
```

Then replace remaining hard-coded text in `SubAgentSettings.vue`, `UserSettings.vue`, and `PersonalitySettings.vue`.

- [ ] **Step 4: Run the focused settings test and a build**

Run:

```bash
npm run test:unit -- src/views/SettingsView.spec.ts
npm run build
```

Expected: PASS, and the build stays green after the first page group migration.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SettingsView.vue frontend/src/views/ModelsView.vue frontend/src/views/ToolsView.vue frontend/src/components/settings/SubAgentSettings.vue frontend/src/components/settings/UserSettings.vue frontend/src/components/settings/PersonalitySettings.vue frontend/src/i18n/index.ts
git commit -m "feat: localize settings models and tools pages"
```

### Task 4: Complete Meeting, Knowledge, and BI Localization

**Files:**
- Modify: `frontend/src/views/MeetingView.vue`
- Modify: `frontend/src/components/meeting/AudioUploader.vue`
- Modify: `frontend/src/components/meeting/MeetingSettings.vue`
- Modify: `frontend/src/components/meeting/RecordingPanel.vue`
- Modify: `frontend/src/components/meeting/TranscriptionList.vue`
- Modify: `frontend/src/components/meeting/TranscriptionDetail.vue`
- Modify: `frontend/src/views/BiAnalyticsView.vue`
- Modify: `frontend/src/components/bi/DataSourceSettings.vue`
- Modify: `frontend/src/components/bi/SchemaAnnotator.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/components/knowledge/DocumentUploader.vue`

- [ ] **Step 1: Write a failing meeting-flow localization test**

Create `frontend/src/components/meeting/TranscriptionList.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { useI18n } from '@/i18n'
import TranscriptionList from './TranscriptionList.vue'

describe('TranscriptionList', () => {
  it('switches empty-state copy with locale', async () => {
    const wrapper = mount(TranscriptionList, {
      props: { transcriptions: [], selectedId: '' },
    })

    expect(wrapper.text()).toContain('暂无转录记录')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('No transcriptions yet')
  })
})
```

- [ ] **Step 2: Run the focused meeting spec to verify it fails**

Run:

```bash
npm run test:unit -- src/components/meeting/TranscriptionList.spec.ts
```

Expected: FAIL because the meeting components still contain hard-coded copy.

- [ ] **Step 3: Localize the meeting, knowledge, and BI group**

Replace hard-coded prompts and alerts in `frontend/src/views/MeetingView.vue`:

```ts
import { useI18n } from '@/i18n'
const { t } = useI18n()

alert(t('meeting.deleteFailed'))
console.error(t('meeting.historyLoadFailed'), e)
```

Then migrate visible copy in these components:

```text
frontend/src/components/meeting/AudioUploader.vue
frontend/src/components/meeting/MeetingSettings.vue
frontend/src/components/meeting/RecordingPanel.vue
frontend/src/components/meeting/TranscriptionList.vue
frontend/src/components/meeting/TranscriptionDetail.vue
frontend/src/components/knowledge/KnowledgeManager.vue
frontend/src/components/knowledge/DocumentUploader.vue
frontend/src/components/bi/DataSourceSettings.vue
frontend/src/components/bi/SchemaAnnotator.vue
frontend/src/views/BiAnalyticsView.vue
```

Add corresponding keys to `frontend/src/i18n/index.ts` using page-prefixed namespaces such as:

```text
meeting.*
knowledge.*
bi.*
dataSource.*
schemaAnnotator.*
```

Convert any count/status string assembly to parameterized calls, for example:

```ts
t('meeting.historyCount', { count: transcriptions.length })
t('knowledge.uploadSuccess', { count: uploadedCount })
```

- [ ] **Step 4: Run the meeting spec and a build**

Run:

```bash
npm run test:unit -- src/components/meeting/TranscriptionList.spec.ts
npm run build
```

Expected: PASS with the new empty-state switch test green and the app still building.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MeetingView.vue frontend/src/components/meeting/AudioUploader.vue frontend/src/components/meeting/MeetingSettings.vue frontend/src/components/meeting/RecordingPanel.vue frontend/src/components/meeting/TranscriptionList.vue frontend/src/components/meeting/TranscriptionDetail.vue frontend/src/views/BiAnalyticsView.vue frontend/src/components/bi/DataSourceSettings.vue frontend/src/components/bi/SchemaAnnotator.vue frontend/src/components/knowledge/KnowledgeManager.vue frontend/src/components/knowledge/DocumentUploader.vue frontend/src/i18n/index.ts frontend/src/components/meeting/TranscriptionList.spec.ts
git commit -m "feat: localize meeting knowledge and bi flows"
```

### Task 5: Complete Memory, Chat, and Navigation/Notification Localization

**Files:**
- Modify: `frontend/src/views/MemoryView.vue`
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/components/layout/Sidebar.vue`
- Modify: `frontend/src/components/memory/RecentMemoryTab.vue`
- Modify: `frontend/src/components/memory/LongtermMemoryTab.vue`
- Modify: `frontend/src/components/memory/AllMemoryTab.vue`
- Modify: `frontend/src/components/memory/MemoryCard.vue`
- Modify: `frontend/src/components/memory/CompressDialog.vue`
- Modify: `frontend/src/components/memory/MergePreviewDialog.vue`
- Modify: `frontend/src/components/chat/ChatPanel.vue`
- Modify: `frontend/src/components/chat/ReminderBellButton.vue`
- Modify: `frontend/src/components/chat/ReminderNotificationsDrawer.vue`
- Modify: `frontend/src/components/chat/PlanCard.vue`
- Modify: `frontend/src/components/chat/TaskCard.vue`

- [ ] **Step 1: Write a failing navigation/chat localization test**

Create `frontend/src/components/layout/Sidebar.i18n.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { useI18n } from '@/i18n'
import Sidebar from './Sidebar.vue'

describe('Sidebar i18n', () => {
  it('switches navigation labels with locale', async () => {
    const wrapper = mount(Sidebar, {
      global: {
        stubs: ['RouterLink', 'RouterView'],
      },
    })

    expect(wrapper.text()).toContain('聊天')
    expect(wrapper.text()).toContain('记忆管理')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('Chat')
    expect(wrapper.text()).toContain('Memory')
  })
})
```

- [ ] **Step 2: Run the navigation/chat spec to verify it fails**

Run:

```bash
npm run test:unit -- src/components/layout/Sidebar.i18n.spec.ts
```

Expected: FAIL if sidebar, reminders, or memory/chat helper text still include hard-coded labels.

- [ ] **Step 3: Localize the memory/chat/navigation group**

Replace remaining hard-coded text in:

```text
frontend/src/views/MemoryView.vue
frontend/src/views/ChatView.vue
frontend/src/components/layout/Sidebar.vue
frontend/src/components/memory/RecentMemoryTab.vue
frontend/src/components/memory/LongtermMemoryTab.vue
frontend/src/components/memory/AllMemoryTab.vue
frontend/src/components/memory/MemoryCard.vue
frontend/src/components/memory/CompressDialog.vue
frontend/src/components/memory/MergePreviewDialog.vue
frontend/src/components/chat/ChatPanel.vue
frontend/src/components/chat/ReminderBellButton.vue
frontend/src/components/chat/ReminderNotificationsDrawer.vue
frontend/src/components/chat/PlanCard.vue
frontend/src/components/chat/TaskCard.vue
```

Use namespaced keys such as:

```text
memory.*
chat.*
reminder.*
planCard.*
taskCard.*
```

Normalize confirm and toast flows:

```ts
confirm(t('chat.deleteConfirm'))
toast.success(t('chat.sessionDeleted'))
toast.error(t('chat.uploadFailed'))
```

Make sure toggle labels and collapsed quick actions in `Sidebar.vue` use `t()` everywhere.

- [ ] **Step 4: Run the sidebar test and the existing reminder/chat specs**

Run:

```bash
npm run test:unit -- src/components/layout/Sidebar.i18n.spec.ts src/components/chat/reminder-notifications.spec.ts
```

Expected: PASS with navigation labels and reminder drawer text switching correctly.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MemoryView.vue frontend/src/views/ChatView.vue frontend/src/components/layout/Sidebar.vue frontend/src/components/memory/RecentMemoryTab.vue frontend/src/components/memory/LongtermMemoryTab.vue frontend/src/components/memory/AllMemoryTab.vue frontend/src/components/memory/MemoryCard.vue frontend/src/components/memory/CompressDialog.vue frontend/src/components/memory/MergePreviewDialog.vue frontend/src/components/chat/ChatPanel.vue frontend/src/components/chat/ReminderBellButton.vue frontend/src/components/chat/ReminderNotificationsDrawer.vue frontend/src/components/chat/PlanCard.vue frontend/src/components/chat/TaskCard.vue frontend/src/i18n/index.ts frontend/src/components/layout/Sidebar.i18n.spec.ts
git commit -m "feat: localize memory chat and navigation surfaces"
```

### Task 6: Final Regression, Diagnostics, and Preview Verification

**Files:**
- Modify if needed after diagnostics: any of the files above

- [ ] **Step 1: Run diagnostics on all recently touched Vue and TS files**

Check diagnostics for:

```text
frontend/src/i18n/index.ts
frontend/src/router/index.ts
frontend/src/components/layout/DesktopShell.vue
frontend/src/views/SettingsView.vue
frontend/src/views/ModelsView.vue
frontend/src/views/ToolsView.vue
frontend/src/views/MeetingView.vue
frontend/src/views/BiAnalyticsView.vue
frontend/src/views/MemoryView.vue
frontend/src/views/ChatView.vue
frontend/src/components/layout/Sidebar.vue
frontend/src/components/meeting/AudioUploader.vue
frontend/src/components/meeting/MeetingSettings.vue
frontend/src/components/meeting/RecordingPanel.vue
frontend/src/components/meeting/TranscriptionList.vue
frontend/src/components/meeting/TranscriptionDetail.vue
frontend/src/components/knowledge/KnowledgeManager.vue
frontend/src/components/knowledge/DocumentUploader.vue
frontend/src/components/bi/DataSourceSettings.vue
frontend/src/components/bi/SchemaAnnotator.vue
frontend/src/components/memory/RecentMemoryTab.vue
frontend/src/components/memory/LongtermMemoryTab.vue
frontend/src/components/memory/AllMemoryTab.vue
frontend/src/components/memory/MemoryCard.vue
frontend/src/components/memory/CompressDialog.vue
frontend/src/components/memory/MergePreviewDialog.vue
frontend/src/components/chat/ChatPanel.vue
frontend/src/components/chat/ReminderBellButton.vue
frontend/src/components/chat/ReminderNotificationsDrawer.vue
frontend/src/components/chat/PlanCard.vue
frontend/src/components/chat/TaskCard.vue
```

Expected: no new diagnostics caused by the i18n migration.

- [ ] **Step 2: Run the focused unit suite**

Run:

```bash
npm run test:unit -- \
  src/i18n/index.spec.ts \
  src/components/layout/DesktopShell.spec.ts \
  src/views/SettingsView.spec.ts \
  src/components/meeting/TranscriptionList.spec.ts \
  src/components/layout/Sidebar.i18n.spec.ts \
  src/components/chat/reminder-notifications.spec.ts
```

Expected: PASS with coverage across the helper, shell, representative pages, and notification/navigation flows.

- [ ] **Step 3: Run the production build**

Run:

```bash
npm run build
```

Expected: PASS with only pre-existing chunk-size warnings acceptable.

- [ ] **Step 4: Start preview and verify every primary page in both locales**

Run:

```bash
npm run dev -- --host 127.0.0.1 --port 4175
```

Manual checklist:

```text
1. Switch zh -> en in Sidebar
2. Check /, /memory, /models, /tools, /bi, /meeting, /knowledge, /settings/subagents, /settings/users
3. On each page confirm: title, subtitle, action buttons, placeholders, empty states, dialogs, and toast/confirm copy switch
4. Switch en -> zh and repeat spot checks
5. Confirm no obvious hard-coded Chinese or English remains in core flows
```

Expected: all primary pages switch cleanly in both directions without stale header text or mixed-language dialogs.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/i18n/index.ts frontend/src/i18n/index.spec.ts frontend/src/router/index.ts frontend/src/components/layout/DesktopShell.vue frontend/src/components/layout/DesktopShell.spec.ts frontend/src/views/SettingsView.vue frontend/src/views/ModelsView.vue frontend/src/views/ToolsView.vue frontend/src/views/MeetingView.vue frontend/src/views/BiAnalyticsView.vue frontend/src/views/MemoryView.vue frontend/src/views/ChatView.vue frontend/src/components/layout/Sidebar.vue frontend/src/components/settings/SubAgentSettings.vue frontend/src/components/settings/UserSettings.vue frontend/src/components/settings/PersonalitySettings.vue frontend/src/components/meeting/AudioUploader.vue frontend/src/components/meeting/MeetingSettings.vue frontend/src/components/meeting/RecordingPanel.vue frontend/src/components/meeting/TranscriptionList.vue frontend/src/components/meeting/TranscriptionDetail.vue frontend/src/components/knowledge/KnowledgeManager.vue frontend/src/components/knowledge/DocumentUploader.vue frontend/src/components/bi/DataSourceSettings.vue frontend/src/components/bi/SchemaAnnotator.vue frontend/src/components/memory/RecentMemoryTab.vue frontend/src/components/memory/LongtermMemoryTab.vue frontend/src/components/memory/AllMemoryTab.vue frontend/src/components/memory/MemoryCard.vue frontend/src/components/memory/CompressDialog.vue frontend/src/components/memory/MergePreviewDialog.vue frontend/src/components/chat/ChatPanel.vue frontend/src/components/chat/ReminderBellButton.vue frontend/src/components/chat/ReminderNotificationsDrawer.vue frontend/src/components/chat/PlanCard.vue frontend/src/components/chat/TaskCard.vue frontend/src/views/SettingsView.spec.ts frontend/src/components/meeting/TranscriptionList.spec.ts frontend/src/components/layout/Sidebar.i18n.spec.ts
git commit -m "feat: complete bilingual coverage across primary frontend pages"
```

---

## Self-Review

- **Spec coverage:** The plan covers the i18n helper, route-key desktop headers, page-level localization across all primary pages, toast/confirm cleanup, and both automated and manual verification.
- **Placeholder scan:** Removed vague “localize remaining strings” style steps and replaced them with explicit file lists, commands, representative snippets, and expected outcomes.
- **Type consistency:** The same key model is used across tasks: `desktopTitleKey`, `desktopSubtitleKey`, `t(key, params)`, page-prefixed namespaces, and `common.*` shared keys.
