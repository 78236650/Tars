# TARS 版本对照（SSOT）

> **单一真相源**：对外说明「当前是什么版本」以本文件为准；`changelog` / `release-notes` / 根 `README` 均引用此处。

## 当前

| 项 | 值 |
|----|-----|
| **平台版本** | **v4.3.2** |
| **OpenAPI** | `backend/tars/main.py` → `4.3.2` |
| **InsightForge 能力** | **INS-2.1.0**（`GET /api/insight/version`） |
| **上一平台 patch** | v4.3.1 |
| **稳定部署参考** | v4.1.2 |

## Git 分支说明

| 名称 | 含义 |
|------|------|
| **产品版本** | v4.3.2（本文件、OpenAPI、发布说明） |
| **当前开发分支** | `v4.3.1`（历史命名，**已包含 v4.3.2 全部提交**） |
| **建议** | 新克隆以 `v4.3.1` 分支为准；后续可重命名为 `v4.3.2` 与产品号对齐 |

勿用 Git 分支名推断功能归属；以 [changelog](./changelog.md) 与 [v4.3.2 发布说明](./v4.3.2-release-notes.md) 为准。

## v4.3.x patch 能力包

| 版本 | 主题 | 要点 |
|------|------|------|
| **v4.3.2** | Superpowers + Wiki | Skill 路由、Plan 门控、Verification Gate；**LLM Wiki + RAG 双通路**（`read_wiki` / `write_wiki`） |
| **v4.3.1** | 会议 + 知识库 + BI | 深度入库、ASR/摘要、BI 数据源、INS-2.1 画像性能 |
| **v4.3.0** | Channels & Execution | ChannelRouter、Cron 全类型、工具审批、Handoff |

更早版本见 [changelog](./changelog.md)。

## 双轨版本（平台 vs 鉴数）

| TARS 平台 | InsightForge | 说明 |
|-----------|--------------|------|
| v4.3.2 | INS-2.1.0 | 当前 |
| v4.3.1 | INS-2.1.0 | 建档性能 patch |
| v4.2.0 | INS-2.0.0 | Data Copilot |

能力 Git tag 建议：`insight-v2.1.0`（不替代平台分支名）。

## 文档入口

| 场景 | 文档 |
|------|------|
| 版本变更全文 | [changelog.md](./changelog.md) |
| v4.3.2 发布 | [v4.3.2-release-notes.md](./v4.3.2-release-notes.md) |
| 从 4.3.1 升级 | [UPGRADE_GUIDE_v4.3.2.md](../UPGRADE_GUIDE_v4.3.2.md) |
| 用 Wiki | [guides/wiki-user.md](../guides/wiki-user.md) |
| 写 Skill | [SKILL_AUTHORING.md](../SKILL_AUTHORING.md) |
| 部署 | [04-运维文档/deployment.md](../04-运维文档/deployment.md) |
| 设计稿索引 | [superpowers/README.md](../superpowers/README.md) |

---

*更新日期：2026-05-26*
