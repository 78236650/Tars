# TARS v4.3.2 操作手册（稳定版）

> 面向运维与内网管理员。版本以 [VERSION.md](../01-项目概览/VERSION.md) 为准。

## 1. 系统要求

| 项 | 要求 |
|----|------|
| OS | Linux / macOS / Windows WSL2 |
| Python | **3.11+**（推荐 3.11） |
| Node | **18+**（仅构建前端时需要） |
| 内存 | 8GB+ 推荐（含 Ollama 时另计模型） |
| 磁盘 | 10GB+（模型、向量库、录音、Wiki） |
| 网络 | 内网即可；调用云端 LLM 时需出站 |

## 2. 安装部署

### 2.1 获取代码

```bash
git clone <repo-url> TARS && cd TARS
git checkout v4.3.2
# 可选：git tag v4.3.2-stable  # 发布打标
```

### 2.2 后端

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 编辑 API Key / Ollama
```

### 2.3 前端（生产）

```bash
cd frontend
npm ci
npm run build          # 产物 dist/
```

生产可由 Nginx 托管 `frontend/dist`，API/WS 反代到 `8000`（见 [deploy/README.md](../../deploy/README.md)）。

### 2.4 启动后端（生产）

```bash
cd backend && source venv/bin/activate
# Insight SSE / 多租户会话：必须单 worker
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

或使用 systemd / `deploy/docker-compose.yml`。

### 2.5 首次验证

| 检查项 | 期望 |
|--------|------|
| `GET /docs` | OpenAPI **4.3.2** |
| `GET /api/insight/version` | **INS-2.1.0**（模块开启时） |
| 登录 Admin | 默认 `admin`，**立即改密** |
| 知识库 → Wiki Tab | 可打开（空库正常） |
| 聊天 `/help` | 命令列表正常 |

完整清单：[v4.3.2-stable-release-checklist.md](../04-运维文档/v4.3.2-stable-release-checklist.md)

## 3. 配置清单

### 3.1 `backend/config/modules.yaml`

| 模块 | 生产建议 | 说明 |
|------|----------|------|
| `knowledge` | `true` | RAG + Wiki 路由 |
| `skillhub` | `true` | 技能市场 |
| `meeting` | 按需 | 需 ASR 模型与磁盘 |
| `bi` / `insight` | 按需 | 鉴数需数据源 |
| `skill_routing` | `true` | v4.3.2 Skill 路由 |
| `plan_gate` | `true` | 复杂计划需审批 |
| `verification` | `true` | 计划完成后 verify |

关闭某项：`enabled: false` 后重启后端。

### 3.2 `backend/config/tool_permissions.yaml`

- `user` 角色需含 `read_wiki`、`write_wiki`（v4.3.2 默认已含）
- 限制 `shell` / `file_write` 给管理员或专用角色

### 3.3 环境变量（`backend/.env`）

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
# DEEPSEEK_API_KEY=...
# TARS_SSE_STICKY=1          # 多实例 Insight 时
```

## 4. 持久化与备份

| 路径 | 内容 |
|------|------|
| `backend/data/*.db` | SQLite 主库 |
| `backend/data/wiki/` | Wiki Markdown |
| `backend/data/vectorstore/` | 向量索引（若启用） |
| `~/.tars/workspaces/{tenant}/` | 租户工作区文件 |

```bash
# 备份示例（停服或低峰）
tar -czf tars-backup-$(date +%Y%m%d).tar.gz \
  backend/data/ backend/config/ skills/tenants/
```

恢复：解压到同路径后重启后端。

## 5. 日常运维

### 5.1 启停

```bash
# 开发热重载
uvicorn tars.main:app --reload --port 8000

# 生产（无 reload）
uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

详见 [服务启动指南.md](../服务启动指南.md)。

### 5.2 日志

- 后端：终端 / systemd journal / `deploy` 容器 `docker compose logs -f backend`
- 审计：Admin → 审计日志，或 `GET /api/audit/logs`

### 5.3 技能热加载

```bash
# 修改 skills/ 后
curl -X POST http://localhost:8000/api/skills/reload \
  -H "Authorization: Bearer <token>"
```

### 5.4 Wiki 运维

- 数据目录：`backend/data/wiki/`
- 勿手动删 `index.md`；页面由 `write_wiki` 或上传编译维护
- 用户指南：[wiki-user.md](./wiki-user.md)

## 6. 升级

| 自版本 | 文档 |
|--------|------|
| v4.3.1 → v4.3.2 | [UPGRADE_GUIDE_v4.3.2.md](../UPGRADE_GUIDE_v4.3.2.md) |
| 更老版本 | 先升到 4.3.1，再升 4.3.2 |

```bash
git fetch && git checkout v4.3.2
cd backend && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
# 重启后端；浏览器强刷前端缓存
```

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| OpenAPI 不是 4.3.2 | 确认分支与重启的是当前 venv |
| Wiki Tab 空 | 正常；用 `write_wiki` 或上传 `target=wiki` |
| 工具调用失败 `~/path` | 技能应使用 workspace 相对路径 |
| Plan 一直待审批 | 确认 WebSocket 连接；或 `plan_gate.fallback_auto_approve` |
| Insight SSE 乱序 | `--workers 1` 或 `TARS_SSE_STICKY=1` |
| BI 查询失败 | `bi_list_datasources` 取真实 UUID；检查 DB 连通 |

## 8. 相关文档

- [deployment.md](../04-运维文档/deployment.md)
- [insightforge-deploy.md](../04-运维文档/insightforge-deploy.md)
- [SECURITY_GUIDE.md](../SECURITY_GUIDE.md)

---

*平台文档对齐: TARS v4.3.2 · [VERSION.md](../01-项目概览/VERSION.md) · 更新: 2026-05-26*
