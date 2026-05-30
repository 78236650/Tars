# TARS v5.0.0 — 升级指南（多用户协作 + Postgres）

> 版本对照：[01-项目概览/VERSION.md](./01-项目概览/VERSION.md)  
> 发布说明：[v5.0.0-release-notes.md](./01-项目概览/v5.0.0-release-notes.md)  
> 设计 SSOT：[superpowers/plans/2026-05-30-tars-v5.0.0-multiuser-design.md](./superpowers/plans/2026-05-30-tars-v5.0.0-multiuser-design.md)

## 适用对象

从 **v4.3.x / v4.4.x / v4.5.x**（SQLite +「每用户一个 tenant_id」）升级到 **v5.0.0**。

| 升级路径 | 适用 |
|----------|------|
| **A. 仅组织池语义（仍用 SQLite）** | 开发机、小规模试点、暂不上 Postgres |
| **B. 生产标准（Postgres + Docker）** | 内网多用户并发、推荐生产 |

两条路径都要做 **组织池数据迁移**（记忆 / 知识库 / Chroma）；路径 B 在此基础上再迁库。

---

## 概述：v5.0.0 改变了什么

1. **身份** — 人类用户走 **JWT**；脚本/集成仍可用 **API Key**。
2. **数据归属** — 全公司一个组织 `org_default`；**shared** 记忆与知识库全员可见；**private** 记忆、会话、个人 core_memory 按 `user_id` 隔离。
3. **不再支持** — 用 `X-Tenant-Id: <user.id>` 切换数据岛；非 admin 不能 impersonate 他人 tenant。
4. **BI / Insight / 计划 / 编排** — 库表里的 `tenant_id` 列仍表示**每用户数据源范围**（等于登录用户的 `user_id`），由 JWT/API Key 自动推导；**无需**再发 `X-Tenant-Id`。管理员代查他人：`?user_id=<uuid>`（需 admin），例如 `GET /api/datasources/`、`/api/insight/datasources/{id}/brief`、`GET /api/plans/` 及计划审批相关路由。
5. **并发** — 生产使用 **PostgreSQL** + **`uvicorn --workers 1`**（多 worker 推迟 v5.1+）。

---

## 升级前准备

### 1. 备份

```bash
# 主库（默认路径）
cp backend/data/tars.db backend/data/tars.db.bak-$(date +%Y%m%d)

# 向量库
tar -czf vectorstore-bak-$(date +%Y%m%d).tar.gz backend/data/vectorstore

# 工作区（人格/进化写回）
tar -czf tars-workspaces-bak-$(date +%Y%m%d).tar.gz ~/.tars/agents ~/.tars/workspaces 2>/dev/null || true
```

### 2. 停机

升级迁移期间停止 backend（避免写入与脚本并发）。

### 3. 依赖

```bash
cd backend
source venv/bin/activate   # 或你的虚拟环境
pip install -r requirements.txt   # 含 PyJWT、psycopg2-binary
```

前端（若用新登录流）：

```bash
cd frontend && npm ci && npm run build
```

---

## 路径 A：SQLite 保留 + 组织池迁移

适合：先验证多用户协作，暂不切换 Postgres。

### A.1 拉取 v5.0.0 代码

```bash
git fetch && git checkout <v5.0.0-tag-or-branch>
```

### A.2 组织池数据迁移（必做）

在 **停服** 状态下，对现有 `tars.db` 执行：

```bash
cd backend

# 1. 记忆：tenant_id → org_default，补 user_id
python3 scripts/migrate_memories_v5_org.py --dry-run
python3 scripts/migrate_memories_v5_org.py

# 2. 知识库 collection tenant 归一
python3 scripts/migrate_knowledge_v5_org.py --dry-run
python3 scripts/migrate_knowledge_v5_org.py

# 3. Chroma 记忆向量（若使用向量检索）
python3 scripts/migrate_chroma_memories_v5_org.py --dry-run
python3 scripts/migrate_chroma_memories_v5_org.py
```

**不要设置** `DATABASE_URL`（或留空），服务仍使用 `backend/data/tars.db`。

### A.3 环境变量（JWT）

在 `backend/.env` 或部署环境中增加：

```bash
# 必填（生产）：随机长密钥，建议 ≥32 字符
TARS_JWT_SECRET=your-long-random-secret-here

# 可选：access token 有效期（小时），默认 24
# TARS_JWT_ACCESS_HOURS=24
```

开发环境未设置时，代码可能使用测试用 fallback——**生产禁止依赖 fallback**。

### A.4 启动

```bash
cd backend
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### A.5 前端 / 客户端

- 用户重新 **账号密码登录**，浏览器会保存 `access_token`。
- 自定义脚本若只发 `X-API-Key` 仍可用；若调知识库/会话等 API，需带 **Bearer** 或确保路由允许 API Key。
- **不要**再依赖 `X-Tenant-Id: <userId>` 访问他人或自己的旧 tenant 岛。

---

## 路径 B：迁移到 PostgreSQL（推荐生产）

在 **路径 A 的 A.2** 之后进行（或先迁 PG 再在 PG 上跑 org 脚本——推荐顺序见下）。

### B.1 启动 Postgres

**Docker Compose（推荐）：**

```bash
cd deploy
cp .env.example .env
# 编辑 .env：TARS_JWT_SECRET、如需改数据库密码
docker compose up -d postgres
# 等待 healthy 后再起 backend
docker compose up -d --build
```

compose 已为 backend 注入：

```text
DATABASE_URL=postgresql://tars:tars@postgres:5432/tars
```

**裸机 Postgres：** 自建库 `tars`，用户授权后：

```bash
export DATABASE_URL=postgresql://tars:YOUR_PASSWORD@127.0.0.1:5432/tars
```

### B.2 导入 SQLite → Postgres

```bash
cd backend
export DATABASE_URL=postgresql://tars:tars@127.0.0.1:5432/tars   # 按实际修改

python3 scripts/migrate_sqlite_to_pg.py --dry-run
python3 scripts/migrate_sqlite_to_pg.py
```

脚本会按表顺序复制数据，并应用 v5 组织池归一逻辑（与 `migrate_memories_v5_org` 一致）。

若 **先** 迁 PG、**后** 才跑 org 脚本：在 PG 上再执行一次 A.2 中的 SQL 类迁移（指向 PG 的 `DATABASE_URL`），或确保 `migrate_sqlite_to_pg` 已包含归一（以仓库脚本为准）。

### B.3 Chroma

向量数据仍在 `backend/data/vectorstore`（或 `TARS_DATA_DIR` 下）。路径 A 的 Chroma 合并脚本在 PG 切换后 **仍要执行一次**（与 DB 引擎无关）。

### B.4 工作区 / Evolution（如有）

若曾使用 `~/.tars/agents/{user_id}/` 与 `~/.tars/workspaces/` 分裂：

- 将组织级 `SOUL.md` / `AGENTS.md` 放到 `~/.tars/workspaces/org_default/`
- 用户级 `USER.md` 可保留 per-user 子目录或依赖 DB `core_memory_blocks`（v5 已按 user 隔离）

发版后首次登录可人工核对进化写回是否生效。

### B.5 启动参数（方案 A）

```bash
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**禁止**在生产使用 `--workers 2` 及以上，除非已完成 v5.1+ 的跨进程状态方案（T3.5）。

---

## 配置对照表

| 变量 | v4.x 常见 | v5.0.0 |
|------|-----------|--------|
| `DATABASE_URL` | 无（SQLite 文件） | 生产：`postgresql://...` |
| `TARS_JWT_SECRET` | 无 | **生产必填** |
| `TARS_PG_POOL_MAX` | 无 | 可选，默认 10 |
| `X-Tenant-Id` | `user.id` | **忽略**，固定 `org_default` |
| 登录响应 | 仅 `api_key` | `access_token` + `api_key` |

---

## 行为变化（给业务与集成方）

### 记忆

| scope | 谁能看见 |
|-------|----------|
| `shared` | 组织内所有登录用户 |
| `private` | 仅 `user_id` 对应用户 |

写入 shared 记忆后，调度员录入的港航信息可被船务账号检索到（验收重点）。

### 知识库

- 所有 `document_collections` 归属 `org_default`。
- API 需 **JWT**（或受支持的 API Key）；不再用 Header 切换 per-user 知识岛。

### 会话

- 列表/详情仅当前用户的 session。
- 未登录访问会话 API → 401。

### 集成 `/api/invoke`

- 仍支持 Bearer API Key。
- 数据作用域为 `org_default`（不再是 `user.id` 作为 tenant）。

---

## 升级后验收

```bash
cd backend
python3 -m pytest tests/test_memory_org_scope.py \
  tests/test_knowledge_org_scope.py \
  tests/test_session_user_scope.py \
  tests/test_auth_jwt_principal.py -q
```

人工检查：

1. 用户 A、B 各登录，会话列表互不可见。
2. A 写 **shared** 记忆或上传知识库 → B 能搜到。
3. A 的 **private** 记忆 B 搜不到。
4. OpenAPI `/docs` 显示版本 **5.0.0**。
5. Postgres 路径：两用户同时操作无 `database is locked`。

---

## 回滚

| 场景 | 做法 |
|------|------|
| 仅代码回退 | 恢复 v4.x 分支 + 还原 `tars.db` / vectorstore 备份 |
| 已跑 org 迁移 | 必须用 **升级前** 的 `tars.db.bak`；迁移脚本不保证可逆 |
| 已迁 Postgres | 保留 PG 卷备份；或继续用 SQLite 备份在 v4 代码上运行 |

JWT 与 org 语义与 v4 **不兼容**，不建议「只回滚前端、保留 v5 库」。

---

## 常见问题

### Q: 升级后登录 401？

- 检查 `TARS_JWT_SECRET` 是否与签发时一致（轮换密钥会使旧 token 失效）。
- 前端清 localStorage 后重新登录。

### Q: 用户看不到以前的 shared 记忆？

- 确认已跑 `migrate_memories_v5_org.py`。
- 旧数据若 `scope=private` 且 tenant 曾为 `user.id`，迁移后仅该 `user_id` 可见；需业务上改为 shared 或重新写入。

### Q: 知识库为空或 B 看不到 A 的文档？

- 确认 `migrate_knowledge_v5_org.py` 已执行。
- 确认 B 请求带 Bearer，且未再传错误的 `X-Tenant-Id`。

### Q: 能否继续多 worker？

- v5.0.0 **不支持**。审批、handoff、follow-up 状态在进程内；多 worker 会随机失败。见 [deploy/README.md](../deploy/README.md)。

### Q: 开发机不想装 Postgres？

- 走路径 **A** 即可；`DATABASE_URL` 不设置。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [v5.0.0-release-notes.md](./01-项目概览/v5.0.0-release-notes.md) | 功能摘要与破坏性变更 |
| [deploy/README.md](../deploy/README.md) | Docker / 裸机部署 |
| [04-运维文档/deployment.md](./04-运维文档/deployment.md) | 运维详解 |
| [port-operations-user-guide.md](./04-运维文档/port-operations-user-guide.md) | v4.4+ 作业调度（能力保留） |

---

*文档版本: v5.0.0 · 更新日期: 2026-05-30*
