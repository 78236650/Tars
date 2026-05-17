# Task4 Meeting Knowledge BI Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `Meeting`、`Knowledge`、`BI` 相关前端视图与组件补齐双语文案覆盖，并以 1 个 `Meeting` 代表性失败测试驱动最小实现。

**Architecture:** 复用现有 `frontend/src/i18n/index.ts` 的轻量字典式国际化方案，不引入新依赖。以 `TranscriptionList` 的空态文案切换测试作为代表性入口，随后只替换目标页面中的硬编码可见文案、错误提示与状态文本，保证构建与目标测试通过。

**Tech Stack:** Vue 3, TypeScript, Vitest, Vue Test Utils, Vite

---

### Task 1: Meeting 代表性失败测试与最小实现

**Files:**
- Create: `frontend/src/components/meeting/TranscriptionList.spec.ts`
- Modify: `frontend/src/components/meeting/TranscriptionList.vue`
- Modify: `frontend/src/views/MeetingView.vue`
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: 写失败测试**

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

    setLocale('zh')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npm run test:unit -- src/components/meeting/TranscriptionList.spec.ts`
Expected: FAIL，因 `TranscriptionList.vue` 仍是硬编码中文。

- [ ] **Step 3: 做最小实现**

```ts
import { useI18n } from '@/i18n'

const { t, locale } = useI18n()
```

将 `TranscriptionList.vue` 中空态、状态文本、删除确认、未知文件、时长/日期格式切换到 `t(...)` 与 `locale.value`。

- [ ] **Step 4: 重新跑测试确认通过**

Run: `npm run test:unit -- src/components/meeting/TranscriptionList.spec.ts`
Expected: PASS

### Task 2: 同步覆盖 Knowledge 与 BI 目标组件

**Files:**
- Modify: `frontend/src/components/meeting/AudioUploader.vue`
- Modify: `frontend/src/components/meeting/MeetingSettings.vue`
- Modify: `frontend/src/components/meeting/RecordingPanel.vue`
- Modify: `frontend/src/components/meeting/TranscriptionDetail.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue`
- Modify: `frontend/src/components/knowledge/DocumentUploader.vue`
- Modify: `frontend/src/components/bi/DataSourceSettings.vue`
- Modify: `frontend/src/components/bi/SchemaAnnotator.vue`
- Modify: `frontend/src/views/BiAnalyticsView.vue`
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: 替换 Meeting/Knowledge/BI 目标范围内的可见硬编码文案**

```ts
const { t, locale } = useI18n()
alert(t('meeting.deleteFailed'))
```

覆盖页面标题、按钮、空态、表单标签、placeholder、确认弹窗、错误提示、状态词与计数摘要。

- [ ] **Step 2: 保持最小改动**

```ts
t('bi.queryRunning')
t('knowledge.createFailed', { message })
t('meeting.durationValue', { value: formatTime(seconds.value) })
```

只新增当前任务所需 key，不改动 README、路由、无关页面或 API 行为。

### Task 3: 验证与交付

**Files:**
- Verify: `frontend/src/components/meeting/TranscriptionList.spec.ts`
- Verify: `frontend/package.json`

- [ ] **Step 1: 跑目标测试**

Run: `npm run test:unit -- src/components/meeting/TranscriptionList.spec.ts`
Expected: PASS

- [ ] **Step 2: 跑构建**

Run: `npm run build`
Expected: PASS，`vue-tsc` 与 `vite build` 均成功。

- [ ] **Step 3: 自查**

检查本次改动文件中无 `console.log`、无 `TODO`、无调试残留，且仅限 `Meeting`、`Knowledge`、`BI` 与 `i18n`、目标测试文件。
