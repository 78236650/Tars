# TARS 版本对照（SSOT）

> **单一真相源**：对外说明「当前是什么版本」以本文件为准；`changelog` / `release-notes` / 根 `README` 均引用此处。

## 当前（稳定版）

| 项 | 值 |
|----|-----|
| **平台版本** | **v4.3.4 stable** |
| **OpenAPI** | `backend/tars/main.py` → `4.3.4` |
| **InsightForge 能力** | **INS-2.1.0**（`GET /api/insight/version`） |
| **上一平台 patch** | v4.3.3 |
| **推荐 Git tag** | `v4.3.4` 或 `v4.3.4-stable` |
| **内网新部署** | 直接使用本版本，无需经过 4.3.3 |

## 下一版本（MVP 已交付，待发 tag）

| 项 | 值 |
|----|-----|
| **平台版本** | **v4.4.0** 「港航垂直 + 作业调度」 |
| **状态** | 功能完成；OpenAPI / tag 发版时对齐 `4.4.0` |
| **开发分支** | `ui/v4.3.4` |
| **发布说明** | [v4.4.0-release-notes.md](./v4.4.0-release-notes.md) |
| **用户指南** | [port-operations-user-guide.md](../04-运维文档/port-operations-user-guide.md) |

## Git 分支说明

| 名称 | 含义 |
|------|------|
| **产品版本** | v4.3.4（本文件、OpenAPI、发布说明） |
| **当前开发分支** | `ui/v4.3.4`（与产品版本一致） |
| **说明** | 原 `v4.3.3` 分支已重命名；远程若仍为旧名，首次 push 用 `git push origin v4.3.4` |

勿用 Git 分支名推断功能归属；以 [changelog](./changelog.md) 与 [v4.3.4 发布说明](./v4.3.4-release-notes.md) 为准。

## v4.3.x patch 能力包

| 版本 | 主题 | 要点 |
|------|------|------|
| **v4.4.0** | **港航 + 作业调度（MVP 已交付）** | 编排记忆层、泊位/堆场/船务 Agent、作业调度 UI |
| **v4.3.4** | **当前稳定版** | v4.3.3 加固 + UI/交互优化 |
| **v4.3.3** | Hardening | CI、god-class 拆分、MCP、Evolution 仪表盘 |
| **v4.3.2** | Superpowers + Wiki | Skill 路由、Plan 门控、Verification Gate；**LLM Wiki + RAG 双通路**（`read_wiki` / `write_wiki`） |
| **v4.3.1** | 会议 + 知识库 + BI | 深度入库、ASR/摘要、BI 数据源、INS-2.1 画像性能 |
| **v4.3.0** | Channels & Execution | ChannelRouter、Cron 全类型、工具审批、Handoff |

更早版本见 [changelog](./changelog.md)。

## 双轨版本（平台 vs 鉴数）

| TARS 平台 | InsightForge | 说明 |
|-----------|--------------|------|
| v4.3.4 | INS-2.1.0 | 当前 |
| v4.3.3 | INS-2.1.0 | Hardening |
| v4.3.2 | INS-2.1.0 | Superpowers + Wiki |
| v4.3.1 | INS-2.1.0 | 建档性能 patch |
| v4.2.0 | INS-2.0.0 | Data Copilot |

能力 Git tag 建议：`insight-v2.1.0`（不替代平台分支名）。

## 文档入口

| 场景 | 文档 |
|------|------|
| 版本变更全文 | [changelog.md](./changelog.md) |
| v4.4.0 发布 | [v4.4.0-release-notes.md](./v4.4.0-release-notes.md) |
| 作业调度使用 | [port-operations-user-guide.md](../04-运维文档/port-operations-user-guide.md) |
| v4.3.4 发布 | [v4.3.4-release-notes.md](./v4.3.4-release-notes.md) |
| 从 4.3.3 升级 | [UPGRADE_GUIDE_v4.3.4.md](../UPGRADE_GUIDE_v4.3.4.md) |
| 用 Wiki | [guides/wiki-user.md](../guides/wiki-user.md) |
| 写 Skill | [SKILL_AUTHORING.md](../SKILL_AUTHORING.md) |
| 稳定版部署 | [deploy/README.md](../../deploy/README.md) · [操作手册](../guides/operations-manual.md) |
| 发布验收 | [v4.3.4-stable-release-checklist.md](../04-运维文档/v4.3.4-stable-release-checklist.md) |
| 部署详解 | [04-运维文档/deployment.md](../04-运维文档/deployment.md) |
| 设计稿索引 | [superpowers/README.md](../superpowers/README.md) |

---

*更新日期：2026-05-30*
