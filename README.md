# TARS AI Agent v5.0.1

面向港航企业内网的 **AI Agent 平台**：**单组织多用户协作**（组织共享池 + 个人会话私有）、JWT、Postgres、技能生态、知识库 + **Wiki**、记忆图谱、BI / 鉴数（InsightForge）、会议助手、港航作业调度、Admin 与审计。

| 项 | 值 |
|----|-----|
| **当前稳定版** | **v5.0.0** |
| **Git Tag** | `v5.0.0`（建议） |
| **OpenAPI** | `5.0.0`（`/docs`） |
| **InsightForge** | `INS-2.1.0`（`GET /api/insight/version`） |
| **版本真相源** | [docs/01-项目概览/VERSION.md](docs/01-项目概览/VERSION.md) |
| **发布说明** | [v5.0.0-release-notes.md](docs/01-项目概览/v5.0.0-release-notes.md) |
| **升级指南** | [UPGRADE_GUIDE_v5.0.0.md](docs/UPGRADE_GUIDE_v5.0.0.md)（从 v4.x） |

---

## v5.0.0 核心变更

- **多用户协作** — 全员共享 `org_default` 组织池（shared 记忆、知识库、实体图谱）；会话与 private 数据按用户隔离
- **JWT 登录** — 浏览器 Bearer + WebSocket token；API Key 保留脚本/集成
- **PostgreSQL** — 生产 `DATABASE_URL`；Docker Compose 自带 Postgres；开发仍可用 SQLite
- **并发** — 单 worker（`--workers 1`）；多 worker 推迟 v5.1+

---

## v4.3.4 能力基线（仍包含）

---

## v4.3.4 核心能力

- **Superpowers** — Skill 自动路由（`triggers` / `skip_when`）、Plan 审批门控、Verification Gate
- **LLM Wiki + RAG** — 双通路知识：`read_wiki` / `write_wiki`，上传自动路由，知识库 Wiki Tab
- **知识库深度入库** — 文档画像、浏览、重索引（v4.3.1 基线）
- **会议助手** — ASR、流式转写、摘要、原音频回放
- **BI + 鉴数** — 数据源、只读 SQL、InsightForge Copilot
- **记忆** — Core / Archival / 实体树 / 图谱 / Reflector
- **SkillHub** — bundled + 租户技能、权限引擎
- **安全** — 脱敏、注入防护、审计、角色工具白名单

### v4.4.0 新增（MVP 已交付，见 [发布说明](docs/01-项目概览/v4.4.0-release-notes.md)）

- **作业调度** — 侧栏 `/orchestration`：快捷场景 / 引导填写 / 自由描述
- **港航专家 Agent** — 泊位调度、堆场分配、船务确认协同
- **编排记忆** — 调度任务、子 Agent 产出、共享黑板持久化

用户指南：[port-operations-user-guide.md](docs/04-运维文档/port-operations-user-guide.md)

---

## 快速开始（开发）

```bash
git clone <repo-url> && cd TARS
git checkout v4.3.2

cp .env.example .env                    # 根目录 LLM 配置
cp backend/.env.example backend/.env  # 可选

cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --reload

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

验证：`http://localhost:8000/docs` 显示 **4.3.4**；默认管理员见启动日志。

**生产 / 内网稳定部署** → [deploy/README.md](deploy/README.md) · [操作手册](docs/guides/operations-manual.md)

---

## 文档导航

| 我是… | 文档 |
|--------|------|
| **部署稳定版** | [deploy/README.md](deploy/README.md) · [部署指南](docs/04-运维文档/deployment.md) · [发布验收清单](docs/04-运维文档/v4.3.4-stable-release-checklist.md) |
| **日常运维** | [操作手册](docs/guides/operations-manual.md) · [服务启动](docs/服务启动指南.md) |
| **从 4.3.3 升级** | [UPGRADE_GUIDE_v4.3.4.md](docs/UPGRADE_GUIDE_v4.3.4.md) |
| **用 Wiki** | [wiki-user.md](docs/guides/wiki-user.md) |
| **写 Skill** | [SKILL_AUTHORING.md](docs/SKILL_AUTHORING.md) |
| **版本 / 变更** | [VERSION.md](docs/01-项目概览/VERSION.md) · [Changelog](docs/01-项目概览/changelog.md) · [v4.4.0 发布说明](docs/01-项目概览/v4.4.0-release-notes.md)（港航作业调度 MVP） |
| **港口作业调度** | [port-operations-user-guide.md](docs/04-运维文档/port-operations-user-guide.md) |
| **鉴数部署** | [insightforge-deploy.md](docs/04-运维文档/insightforge-deploy.md) |
| **全部指南** | [docs/guides/README.md](docs/guides/README.md) |

### 专题指南（根目录）

| 文档 | 说明 |
|------|------|
| [CRONJOB_GUIDE.md](CRONJOB_GUIDE.md) | 定时任务 |
| [EVOLUTION_GUIDE.md](EVOLUTION_GUIDE.md) | 自进化闭环 |
| [SECURITY_GUIDE.md](docs/SECURITY_GUIDE.md) | 安全与审计 |

---

## 版本历史（平台）

> 详细条目见 [changelog](docs/01-项目概览/changelog.md)。下表为 **TARS 平台主版本**摘要。

| 版本 | 日期 | 主题 |
|------|------|------|
| **v4.4.0** | 2026-05 | **港航 MVP** — 作业调度、泊位/堆场/船务 Agent、编排记忆层（功能完成，见 [发布说明](docs/01-项目概览/v4.4.0-release-notes.md)） |
| **v4.3.4** | 2026-05 | **稳定版当前** — v4.3.3 加固 + UI/交互优化 |
| v4.3.1 | 2026-05 | 会议 ASR、知识库深度入库、BI、INS-2.1 画像性能 |
| v4.3.0 | 2026-05 | Channels、Cron 全类型、工具审批、Handoff |
| v4.2.0 | 2026-05 | Data Copilot、Evolution 写回闭环、记忆图谱 |
| v4.1.4 | 2026-05 | 记忆实体树、谱系、关系图 |
| v4.1.0–v4.1.3 | 2026-05 | Skill 生态、SkillHub、体验层、Curator |
| v4.0.x | 2026-05 | Provider 插件、安全加固、Prompt Cache、SkillHub 预览 |
| v2.x–v3.x | 2026-05 | 工具/技能重构、记忆 V3、PDCA、前端演进（归档见 changelog） |

**稳定部署建议**：新环境直接 **v4.3.4**；自 v4.3.3 升级见 [升级指南](docs/UPGRADE_GUIDE_v4.3.4.md)。

---

## 项目结构（精简）

```
TARS/
├── backend/           # FastAPI + Agent + Wiki + Insight + BI
│   ├── tars/          # 应用代码
│   ├── config/        # modules.yaml, providers.yaml, tool_permissions.yaml
│   ├── data/          # SQLite、wiki/、vectorstore（运行时，需备份）
│   └── tests/
├── frontend/          # Vue 3 + Vite
├── skills/            # _global + tenants/{id}/
├── deploy/            # 生产 docker-compose、脚本
├── docs/              # 版本、运维、设计稿
└── scripts/           # 验收、迁移、文档维护
```

---

## 配置要点（v4.3.4）

| 文件 | 作用 |
|------|------|
| `backend/config/modules.yaml` | 会议/BI/知识库/SkillHub；`skill_routing` / `plan_gate` / `verification` |
| `backend/config/providers.yaml` | LLM Provider |
| `backend/config/tool_permissions.yaml` | 角色工具白名单（含 `read_wiki` / `write_wiki`） |
| `backend/.env` | API Key、Ollama 地址等 |

持久化目录（部署必备份）：`backend/data/`（含 DB、`wiki/`、工作区相关数据）。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLite、Chroma、WebSocket |
| 前端 | Vue 3、TypeScript、Tailwind、Vite |
| 模型 | Ollama、OpenAI Compatible（DeepSeek / 通义等） |

---

## 测试

```bash
cd backend
source venv/bin/activate
pytest tests/test_wiki_smoke_e2e.py tests/test_superpowers_v432_e2e.py -q   # v4.3.4 冒烟
pytest tests/ -q --ignore=tests/insight   # 全量（耗时长可分批）
```

---

## 许可证

MIT License
