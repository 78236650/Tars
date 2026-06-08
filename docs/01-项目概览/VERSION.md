# TARS 版本对照（SSOT）

> **单一真相源**：对外说明「当前是什么版本」以本文件为准；`changelog` / `release-notes` / 根 `README` 均引用此处。

## 规划中（未发布）

| 项 | 值 |
|----|-----|
| **v5.0.5** 「安全加固 + 企业级就绪」 | 文档就绪、代码待启动 |
| 由来 | v5.0.4 企业级审计（49 agent，39 条确认问题）|
| 文档入口 | [v5.0.5-README](./v5.0.5-README.md) · [设计](../superpowers/plans/2026-06-07-tars-v5.0.5-security-hardening-design.md) · [开发步骤](../03-实施计划/v5.0.5-development-steps.md) · [执行计划](../03-实施计划/v5.0.5-execution-plan.md) |

> ⚠️ **SSOT 校准待办**：本文件标当前为 v5.0.3，但 `backend/tars/main.py` OpenAPI 已是 `5.0.4`（changelog 亦缺 v5.0.4 条目）。发版 v5.0.5 时需一并补齐 v5.0.4 记录并校准版本号。

## 当前（稳定版）

| 项 | 值 |
|----|-----|
| **平台版本** | **v5.0.3** 「多用户隔离 + DeepSeek + 安全加固」 |
| **OpenAPI** | `backend/tars/main.py` → `5.0.3` |
| **InsightForge 能力** | **INS-2.1.0**（`GET /api/insight/version`） |
| **上一平台 major** | v5.0.1（售前管理模块）；v5.0.0（多用户协作 + 并发底座） |
| **推荐 Git tag** | `v5.0.3` |
| **生产数据库** | **PostgreSQL**（`DATABASE_URL`）；开发可继续 SQLite |

## v5.0.0 要点（2026-05-30）

| 维度 | 内容 |
|------|------|
| 定位 | 单组织多用户（**非** SaaS 多租户） |
| 身份 | JWT + API Key（集成） |
| 数据 | 组织池 `org_default`；private 按 `user_id` |
| 并发 | Postgres + `uvicorn --workers 1` |

发布说明：[v5.0.0-release-notes.md](./v5.0.0-release-notes.md)

## 历史版本（仍可用能力）

| 版本 | 主题 |
|------|------|
| **v4.5.0** | 进出港计划 + Agent/OR 协同 |
| **v4.4.0** | 港航垂直 + 作业调度 MVP |
| **v4.3.4** | Superpowers + Wiki + 加固 |
| **v4.3.0** | Channels & Execution |

完整条目见 [changelog.md](./changelog.md)。

## Git 分支说明

| 名称 | 含义 |
|------|------|
| **产品版本** | v5.0.3（本文件、OpenAPI、发布说明） |
| **开发分支** | 以仓库当前分支为准；发版打 tag `v5.0.3` |

勿用 Git 分支名推断功能归属；以 changelog 与对应 release-notes 为准。

## 双轨版本（平台 vs 鉴数）

| TARS 平台 | InsightForge | 说明 |
|-----------|--------------|------|
| **v5.0.3** | INS-2.1.0 | 当前（多用户隔离 + DeepSeek + 安全加固） |
| v5.0.1 | INS-2.1.0 | 售前管理模块 |
| v5.0.0 | INS-2.1.0 | 多用户协作 + 并发底座 |
| v4.4.0 | INS-2.1.0 | 港航编排 MVP |
| v4.3.4 | INS-2.1.0 | 上一稳定 patch 线 |

能力 Git tag 建议：`insight-v2.1.0`（不替代平台 tag）。

## 文档入口

| 场景 | 文档 |
|------|------|
| 版本变更全文 | [changelog.md](./changelog.md) |
| **v5.0.0 发布** | [v5.0.0-release-notes.md](./v5.0.0-release-notes.md) |
| **从 v4.x 升级到 v5.0** | [UPGRADE_GUIDE_v5.0.0.md](../UPGRADE_GUIDE_v5.0.0.md) |
| v5.0 设计 | [multiuser-design.md](../superpowers/plans/2026-05-30-tars-v5.0.0-multiuser-design.md) |
| v4.4.0 发布 | [v4.4.0-release-notes.md](./v4.4.0-release-notes.md) |
| 作业调度使用 | [port-operations-user-guide.md](../04-运维文档/port-operations-user-guide.md) |
| 稳定版部署 | [deploy/README.md](../../deploy/README.md) |
| 部署详解 | [04-运维文档/deployment.md](../04-运维文档/deployment.md) |
| 设计稿索引 | [superpowers/README.md](../superpowers/README.md) |

---

*更新日期：2026-06-03*
