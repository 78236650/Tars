# TARS v4.3.2 生产部署

> 操作细节见 [操作手册](../docs/guides/operations-manual.md) · 验收 [清单](../docs/04-运维文档/v4.3.2-stable-release-checklist.md)

## 方式一：裸机 / 虚拟机（推荐内网）

### 1. 准备

```bash
git clone <repo-url> /opt/tars && cd /opt/tars
git checkout v4.3.2
```

### 2. 一键脚本（构建 + 提示启动命令）

```bash
./scripts/deploy-stable.sh
```

### 3. 手动步骤

```bash
# 后端
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 编辑

# 前端静态资源
cd ../frontend && npm ci && npm run build

# 启动（生产单 worker）
cd ../backend && source venv/bin/activate
python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Nginx 示例：静态 `frontend/dist`，`/api` 与 `/ws` 反代 `http://127.0.0.1:8000`。

## 方式二：Docker Compose

```bash
cd deploy
cp .env.example .env    # 编辑 LLM 等变量
docker compose up -d --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| backend | 8000 | FastAPI + WebSocket |
| frontend | 8080 | Nginx 托管 dist + 反代 API |

数据卷：`tars-data` → 容器内 `/app/data`（SQLite、Wiki、向量库）。

## 方式三：仅后端 + 外部 Nginx

适合已有反向代理：

1. 按方式一构建 `frontend/dist`
2. 仅运行 backend（8000）
3. Nginx 配置参考 `deploy/nginx.conf`

## 可选组件

| 组件 | 目录 |
|------|------|
| InsightForge 测试库 | [insightforge-db/](./insightforge-db/) |
| SearXNG 私有搜索 | [searxng/](./searxng/) |

## 备份

```bash
docker compose -f deploy/docker-compose.yml exec backend \
  tar -czf - /app/data /app/config > tars-backup.tar.gz
# 裸机：tar -czf tars-backup.tar.gz backend/data backend/config
```

## 升级至 v4.3.2

见 [UPGRADE_GUIDE_v4.3.2.md](../docs/UPGRADE_GUIDE_v4.3.2.md)。

---

*对齐 TARS v4.3.2 · 2026-05-26*
