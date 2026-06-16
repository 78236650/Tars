# TARS v5.0.3 操作手册（稳定版）

> 面向运维与内网管理员。版本以 [VERSION.md](../01-项目概览/VERSION.md) 为准。

## 1. 系统要求

| 项 | 要求 |
|----|------|
| OS | Linux / macOS / Windows WSL2 |
| Python | **3.11+**（推荐 3.12+） |
| Node | **18+**（仅构建前端时需要） |
| 内存 | 8GB+ 推荐（含 Ollama 时另计模型） |
| 磁盘 | 10GB+（模型、向量库、录音、Wiki） |
| 网络 | 内网即可；调用云端 LLM 时需出站 |
| 数据库 | 生产 PostgreSQL 14+（`DATABASE_URL`）；开发 SQLite |

## 2. 安装部署

### 2.1 获取代码

```bash
git clone <repo-url> TARS && cd TARS
git checkout v5.0.3
```

### 2.2 后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 编辑 LLM API Key
```

> 注意虚拟环境目录名是 `.venv`（不是 `venv`），后续所有命令保持一致。

### 2.3 前端（生产）

```bash
cd frontend
npm ci
npm run build          # 产物 dist/
```

生产可由 Nginx 托管 `frontend/dist`，API/WS 反代到 `8000`（见 [deploy/README.md](../../deploy/README.md)）。

### 2.4 启动后端（生产）

```bash
cd backend && source .venv/bin/activate
# Insight SSE / 多用户隔离：必须单 worker
python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

或使用 systemd / `deploy/docker-compose.yml`。

### 2.5 首次验证

| 检查项 | 期望 |
|--------|------|
| `GET /health` | `{"status":"ok","version":"5.0.5"}` |
| `GET /docs` | OpenAPI **5.0.3+** |
| `GET /api/insight/version` | **INS-2.1.0**（模块开启时） |
| 登录 Admin | 默认 `admin`，**立即改密** |
| 知识库 → Wiki Tab | 可打开（空库正常） |
| 聊天 `/help` | 命令列表正常 |

## 3. 配置清单

### 3.1 `backend/.env`

```bash
# 至少配置一个 LLM Provider
# OPENROUTER_API_KEY=sk-or-v1-...
# DEEPSEEK_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...

# Ollama 本地模型（可选）
# OLLAMA_BASE_URL=http://127.0.0.1:11434
# OLLAMA_MODEL=qwen3:8b

# 数据库（生产 PostgreSQL）
# DATABASE_URL=postgresql://user:pass@host:5432/tars

# CORS 白名单
# TARS_CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

### 3.2 `backend/config/modules.yaml`

| 模块 | 生产建议 | 说明 |
|------|----------|------|
| `knowledge` | `true` | RAG + Wiki 路由 |
| `skillhub` | `true` | 技能市场 |
| `meeting` | 按需 | 需 ASR 模型与磁盘 |
| `bi` / `insight` | 按需 | 鉴数需数据源 |
| `skill_routing` | `true` | Skill 自动路由 |
| `plan_gate` | `true` | 复杂计划需审批 |
| `verification` | `true` | 计划完成后 verify |

关闭某项：`enabled: false` 后重启后端。

### 3.3 `backend/config/tool_permissions.yaml`

- `user` 角色需含 `read_wiki`、`write_wiki`
- 限制 `shell` / `file_write` 给管理员或专用角色

## 4. 持久化与备份

| 路径 | 内容 |
|------|------|
| `backend/data/*.db` | SQLite 主库（开发） |
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
# 一键重启
./scripts/restart-tars-dev.sh

# 手动启动后端
cd backend && source .venv/bin/activate
python -m tars.main

# 手动启动前端
cd frontend && npm run dev
```

详见 [服务启动指南.md](../服务启动指南.md)。

### 5.2 日志

- 后端：终端输出 / `backend/nohup-backend.log` / systemd journal
- 前端：终端输出 / `frontend/nohup-frontend.log`
- 审计：Admin → 审计日志，或 `GET /api/audit/logs`

### 5.3 技能热加载

```bash
curl -X POST http://localhost:8000/api/skills/reload \
  -H "Authorization: Bearer <token>"
```

### 5.4 Wiki 运维

- 数据目录：`backend/data/wiki/`
- 勿手动删 `index.md`；页面由 `write_wiki` 或上传编译维护

## 6. 升级

| 自版本 | 文档 |
|--------|------|
| v4.x → v5.0 | [UPGRADE_GUIDE_v5.0.0.md](../UPGRADE_GUIDE_v5.0.0.md) |
| v5.0.x | 按 changelog 增量升级 |

```bash
git fetch && git checkout v5.0.3
cd backend && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
# 重启后端；浏览器强刷前端缓存
```

## 7. 故障排查

| 现象 | 处理 |
|------|------|
| OpenAPI 版本不符 | 确认分支正确、重启的是当前 venv |
| 端口被占用 | `lsof -i :8000` 找进程，`kill` 后重试 |
| 前端 5173 已占用 | Vite 会自动尝试 5174+；或 `--strictPort` |
| Wiki Tab 空 | 正常；用 `write_wiki` 或上传 `target=wiki` |
| 工具调用失败 `~/path` | 技能应使用 workspace 相对路径 |
| Plan 一直待审批 | 确认 WebSocket 连接；或 `plan_gate.fallback_auto_approve` |
| Insight SSE 乱序 | `--workers 1` 或 `TARS_SSE_STICKY=1` |
| BI 查询失败 | `bi_list_datasources` 取真实 UUID；检查 DB 连通 |
| 导入错误 ModuleNotFoundError | `pip install -r requirements.txt`；确认在 `.venv` 中 |

## 8. 相关文档

- [deployment.md](../04-运维文档/deployment.md)
- [insightforge-deploy.md](../04-运维文档/insightforge-deploy.md)
- [SECURITY_GUIDE.md](../SECURITY_GUIDE.md)
- [服务启动指南.md](../服务启动指南.md)

---

*TARS v5.0.3 · [VERSION.md](../01-项目概览/VERSION.md) · 更新: 2026-06-16*