# Superpowers 设计稿索引

本目录为 **设计 spec / 实施 plan** 归档，不是对外发布说明。已交付能力以 [VERSION.md](../01-项目概览/VERSION.md) 与 [changelog](../01-项目概览/changelog.md) 为准。

每个 `.md` 文件头部含 YAML：`doc_type`、`status`（`shipped` / `draft` / `superseded`）、`platform_version`。批量维护脚本：`scripts/tag_superpowers_docs.py`。

## 状态图例

| status | 含义 |
|--------|------|
| `shipped` | 已合入代码，见对应平台版本 release-notes |
| `draft` | 未交付或进行中 |
| `superseded` | 被新版本替代，仅作历史参考 |

## v4.4.0（MVP 已交付）

| 文档 | 类型 | 说明 |
|------|------|------|
| [plans/2026-05-30-portlogistics-agent-memory-design.md](./plans/2026-05-30-portlogistics-agent-memory-design.md) | plan | 编排记忆层 + 垂直模式 Phase 0–4 |
| [plans/2026-05-30-port-agent-fleet-design.md](./plans/2026-05-30-port-agent-fleet-design.md) | plan | 港航 Agent 集群 Phase B–E（MVP） |
| [specs/2026-05-30-smart-port-agent-design.md](./specs/2026-05-30-smart-port-agent-design.md) | spec | 智慧港口长期愿景（非 v4.4.0 范围） |

发布说明：[v4.4.0-release-notes.md](../01-项目概览/v4.4.0-release-notes.md) · 用户指南：[port-operations-user-guide.md](../04-运维文档/port-operations-user-guide.md)

## v4.5.0（计划中）

| 文档 | 类型 | 说明 |
|------|------|------|
| [specs/2026-05-30-vessel-plan-or-design.md](./specs/2026-05-30-vessel-plan-or-design.md) | spec | 进出港计划 Agent+OR（已批准） |
| [plans/2026-05-30-vessel-plan-or-plan.md](./plans/2026-05-30-vessel-plan-or-plan.md) | plan | 实施计划 |

## v4.3.2（已交付）

| 文档 | 类型 | 说明 |
|------|------|------|
| [specs/2026-05-25-skill-routing-plan-gate-design.md](./specs/2026-05-25-skill-routing-plan-gate-design.md) | spec | Skill 路由 + Plan 门控 + Verify |
| [plans/2026-05-25-skill-routing-plan-gate-plan.md](./plans/2026-05-25-skill-routing-plan-gate-plan.md) | plan | 实施任务 |
| [specs/2026-05-25-llm-wiki-rag-dual-path-design.md](./specs/2026-05-25-llm-wiki-rag-dual-path-design.md) | spec | Wiki + RAG 双通路 |
| [plans/2026-05-25-llm-wiki-rag-dual-path-plan.md](./plans/2026-05-25-llm-wiki-rag-dual-path-plan.md) | plan | Wiki 实施任务 |

发布说明：[v4.3.2-release-notes.md](../01-项目概览/v4.3.2-release-notes.md)

## v4.3.1（已交付）

| 文档 | 类型 | 说明 |
|------|------|------|
| [specs/2026-05-24-knowledge-deep-ingest-design.md](./specs/2026-05-24-knowledge-deep-ingest-design.md) | spec | 知识库深度入库 |
| [plans/2026-05-24-knowledge-deep-ingest-plan.md](./plans/2026-05-24-knowledge-deep-ingest-plan.md) | plan | M1–M4 任务 |

## v4.3.0 / v4.2.0（已交付）

| 文档 | 平台版本 |
|------|----------|
| [specs/2026-05-24-openclaw-phase3-design.md](./specs/2026-05-24-openclaw-phase3-design.md) | v4.3.0 |
| [specs/2026-05-24-data-copilot-phase1-design.md](./specs/2026-05-24-data-copilot-phase1-design.md) | v4.2.0 |
| [specs/2026-05-24-evolution-phase2-design.md](./specs/2026-05-24-evolution-phase2-design.md) | v4.2.0 |

## InsightForge（能力线，非平台号）

| 文档 | 能力版本 |
|------|----------|
| [specs/2026-05-20-insightforge-ins-2-redesign.md](./specs/2026-05-20-insightforge-ins-2-redesign.md) | INS-2.0 |
| [specs/2026-05-24-insightforge-profile-perf-design.md](./specs/2026-05-24-insightforge-profile-perf-design.md) | INS-2.1 |

## 更早历史稿

`specs/` 与 `plans/` 下 2026-05-06～05-19 文档多为 v4.0–v4.1 迭代记录；未逐一标注 `status` 时默认 **shipped**（对应当期平台能力）或 **superseded**（已被 v4.3.x 替代）。检索时优先用上表链接。

---

*索引版本：2026-05-30*
