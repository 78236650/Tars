# InsightForge 鉴数 — 实施计划 INS-2.0.0

> **能力 Tag**: `@insight-forge`  
> **Git 里程碑**: `insight-v2.0.0`  
> **预计总工期**: 4–5 周  
> **依赖**: INS-1.0 Profile 已落地；TARS v4.1.x，`bi` + `knowledge` 已启用

---

## 文档索引

| 文档 | 路径 |
|------|------|
| **INS-2.0 产品设计（定稿）** | `docs/superpowers/specs/2026-05-20-insightforge-ins-2-redesign.md` |
| **INS-2.0 实施计划（详细）** | [`docs/superpowers/plans/2026-05-20-insightforge-ins-2-implementation-plan.md`](../superpowers/plans/2026-05-20-insightforge-ins-2-implementation-plan.md) |
| INS-1.0 实施计划 | `docs/03-实施计划/insightforge-ins-v1-implementation-plan.md` |
| INS-1.0 技术详设 | `docs/02-技术方案/insightforge-ins-v1-design.md` |

---

## 里程碑（摘要）

| 阶段 | 交付 |
|------|------|
| **M1** | `InsightWorkflowService` + workflow API + DB 迁移（**不改 UI**） |
| **M2** | `MetricQaEngine` + `/ask` + Chat 卡片 + `eval_set.yaml` |
| **M3** | `WorkflowStrip` V2 + W1 运维台瘦身 |
| **M4** | adopt + feedback + Agent 工具 + `insight_analyst` |
| **M5** | GA、`/admin/insight/llm`、tag `insight-v2.0.0` |

完整 Task 分解、测试命令与提交粒度见 **[详细计划](../superpowers/plans/2026-05-20-insightforge-ins-2-implementation-plan.md)**。

---

## 与 INS-1.0 计划的关系

- INS-1.0 **Phase 0–1（Profile）** 已完成 → 不重复实施。
- INS-1.0 **Phase 2–3（问数 + 工作台）** 由本计划 **M2–M5** 替代并升级（对话优先架构）。
