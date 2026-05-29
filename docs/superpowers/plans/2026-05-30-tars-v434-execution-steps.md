# TARS v4.3.4 执行步骤编排

> **关联计划**: [2026-05-30-tars-v434-ui-plan.md](2026-05-30-tars-v434-ui-plan.md) — 6 任务的逐步代码 + 验证命令 + commit
> **目标**: 把前端从"功能可用但视觉凌乱"收敛为"统一清爽有设计语言",走 A 收敛精修
> **日期**: 2026-05-30
> **版本**: v4.3.4 开发计划

---

## 一、依赖链总览

```
PHASE 1 — token 收口(根因)        PHASE 2 — 原子组件        PHASE 3 — 迁移打磨
┌──────────────────────┐         ┌──────────────────┐      ┌────────────────────┐
│ Task 1 tailwind token│────────►│ Task 3 BaseButton │─────►│ Task 5 替换硬编码色  │
│ Task 2 style.css 变量 │         │ Task 4 Input/Card │      │ Task 6 替换裸 btn    │
│ (1→2 串行)            │         │ (依赖 Task 1 token)│      │ (依赖 P1+P2)        │
└──────────────────────┘         └──────────────────┘      └────────────────────┘
```

- **硬依赖**:Task 1 → 所有后续(token 是地基)。Task 3/4 用 `rounded-card`/`bg-surface-*`,必须 Task 1 先落。
- **可并行**:Task 3 与 Task 4 互不依赖;Task 5 的 4 个批次按域并行皆可。

## 二、三阶段任务明细

### PHASE 1 — token 收口(预计 0.5 天,低风险)

> 把 85 处硬编码棕黑色 + 117 处 slate/stone 混用收口成语义 token。这是"不美观"的根因,改完地基,后面才有意义。

| # | 任务 | 文件变更 | 风险 | 耗时 |
|:---:|------|----------|:---:|:---:|
| 1 | tailwind 语义 token | 改 `tailwind.config.js` | 🟢 低 | 20min |
| 2 | style.css 改 CSS 变量 | 改 `src/style.css` | 🟢 低 | 15min |

**出口**:`npm run build` 通过,新 token(`bg-surface-1` 等)能编译进 CSS。

### PHASE 2 — 原子组件(预计 0.5 天,低风险)

> 抽 3 个原子组件消灭按钮/输入框/卡片的多套写法。**附带修一个真实 bug**:`btn-primary` 全站被引用但无定义。

| # | 任务 | 文件变更 | 风险 | 耗时 |
|:---:|------|----------|:---:|:---:|
| 3 | BaseButton + 定义 btn-* | 建 `BaseButton.vue`+spec;改 `style.css` | 🟢 低 | 40min |
| 4 | BaseInput + BaseCard | 建 `BaseInput.vue`/`BaseCard.vue`+spec | 🟢 低 | 30min |

**出口**:vitest 新增测试全过;`btn-primary` 有定义。

### PHASE 3 — 迁移打磨(预计 1-1.5 天,中风险=体力+回归面)

> 标尺:85 处硬编码色 / 41 文件,117 处 slate/stone 混用。按域分批,每批一 commit + 构建 + 肉眼验证。

| # | 任务 | 文件变更 | 风险 | 耗时 |
|:---:|------|----------|:---:|:---:|
| 5 | 替换硬编码色为 token | 改 41 个 .vue(分 4 批) | 🟡 中 | 3-4h |
| 6 | 裸 btn→BaseButton + 空态 | 建 `EmptyState.vue`;改 8 组件 | 🟡 中 | 2h |

**出口**:硬编码色 grep 清零;build 成功;vitest 零新增失败;三核心界面肉眼一致。

## 三、风险评估

| # | 任务 | 风险 | 最大风险点 | 缓解 |
|:---:|------|:---:|------|------|
| 1 | tailwind token | 🟢 低 | 删 slate/blue 致 117 处炸裂 | **保留 slate/blue 不删**,只加新 token |
| 2 | style.css | 🟢 低 | 变量名笔误致全局失色 | 改完 dev 肉眼比对 |
| 3 | BaseButton | 🟢 低 | btn-* @apply 引用未定义 token | Task 1 先落 token |
| 4 | Input/Card | 🟢 低 | v-model 事件未透传 | spec 验 emit |
| 5 | 硬编码色替换 | 🟡 中 | 漏替/错映射色号 | 每批 grep 验清零 + 肉眼 |
| 6 | 裸 btn 替换 | 🟡 中 | 8 组件 import 遗漏致构建错 | 逐文件 build |

## 四、执行纪律

1. **token 先行**:Task 1 不落,后续全部阻塞——地基优先。
2. **保留 slate/blue**:本轮不强迁 117 处旧引用,避免一次性炸裂;留待后续。
3. **分批替换**:Task 5 按 layout/chat/memory/其余 四批,每批独立 commit + 构建。
4. **肉眼验证不可省**:UI 改动构建过 ≠ 好看,每阶段 dev 跑起来看三核心界面。
5. **不扩范围**:排除项(重塑视觉/响应式/亮色/aria/清旧 token)本轮不碰。

## 五、分支策略

```bash
git checkout v4.3.2
git checkout -b ui/v4.3.4
# 每完成一个 Task / Phase 3 每批 → 一个 commit
git checkout v4.3.2 && git merge --no-ff ui/v4.3.4 && git tag v4.3.4
```

## 六、执行模式(二选一)

1. **子代理逐任务**(推荐)——每 task 派新 subagent,任务间审 diff。适合 Task 5/6 大面积替换。
2. **本会话内批量**——按三阶段跑,每阶段停下看 checkpoint。UI 改动建议你全程在场做肉眼验证。
