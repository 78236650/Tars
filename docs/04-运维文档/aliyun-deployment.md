# TARS v5.0.3 阿里云部署指南

## 1. 服务器准备

### 最低配置

| 资源 | 开发/测试 | 生产推荐 |
|------|----------|---------|
| CPU | 4 核 | 8 核+ |
| 内存 | 8 GB | 16 GB+ |
| 磁盘 | 40 GB 系统盘 | 40 GB 系统盘 + 100 GB 数据盘（挂载到 `/data`） |
| 操作系统 | Ubuntu 22.04 / Alibaba Cloud Linux 3 | 同左 |
| 带宽 | 5 Mbps | 10 Mbps+ |

### 安全组入方向规则

| 端口 | 协议 | 来源 | 说明 |
|------|------|------|------|
| 22 | TCP | 办公 IP | SSH 管理 |
| 80 | TCP | 0.0.0.0/0 | HTTP（Let's Encrypt 验证） |
| 443 | TCP | 0.0.0.0/0 | HTTPS 服务 |

> 后端 8000、SearXNG 8888、ChromaDB 8100 **不要** 对外开放 — 只通过 nginx/caddy 反代访问。

---

## 2. 环境安装

### SSH 登录

```bash
ssh root@<你的ECS公网IP>
```

### 安装 Docker

```bash
# 阿里云镜像加速安装
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun

# 启动并设置开机自启
systemctl enable docker --now

# 安装 Docker Compose v2
apt install -y docker-compose-v2
# 或: curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose

# 验证
docker --version
docker compose version
```

### 挂载数据盘（如果有）

```bash
# 查看磁盘
fdisk -l

# 假设数据盘为 /dev/vdb
mkfs.ext4 /dev/vdb
mkdir -p /data
mount /dev/vdb /data
echo "/dev/vdb /data ext4 defaults 0 0" >> /etc/fstab
```

### 安装 Caddy（HTTPS 反向代理，推荐）

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy

# 启动
systemctl enable caddy --now
```

---

## 3. 部署 TARS

### 克隆项目

```bash
cd /data
git clone https://github.com/your-org/TARS.git
cd TARS
git checkout v5.0.3
```

### 配置环境变量

```bash
cd deploy
cp .env.example .env
nano .env
```

**必须修改的配置**：

```ini
# ── 端口 ──
TARS_BACKEND_PORT=8000
TARS_FRONTEND_PORT=8080

# ── PostgreSQL 密码 ──
PG_USER=tars
PG_PASSWORD=<生成强密码>
PG_DATABASE=tars
DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@postgres:5432/${PG_DATABASE}
TARS_PG_POOL_MAX=10

# ── JWT 密钥（必须改！）──
# 生成: openssl rand -hex 32
TARS_JWT_SECRET=<替换为随机32字节hex>

# ── LLM 配置 ──
# 方案A: 阿里云百炼 API（推荐国内使用）
# 在 backend/config/providers.yaml 添加 qwen 配置，或通过环境变量注入

# 方案B: 自建 Ollama（需要 GPU 服务器）
OLLAMA_BASE_URL=http://<GPU服务器IP>:11434
OLLAMA_MODEL=qwen3:8b

# 方案C: DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# ── 文件上传限制 ──
TARS_MAX_UPLOAD_MB=50
```

### 配置 LLM Provider

编辑 `backend/config/providers.yaml`，添加阿里云百炼（通义千问）：

```yaml
providers:
  # 阿里云百炼（推荐）
  qwen:
    type: openai_compat
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    default_model: qwen-plus
    api_key: "${DASHSCOPE_API_KEY}"
    display_name: "通义千问"

  # DeepSeek（备选）
  deepseek:
    type: openai_compat
    base_url: https://api.deepseek.com/v1
    default_model: deepseek-chat
    api_key: "${DEEPSEEK_API_KEY}"
    display_name: "DeepSeek"
```

### 启动

```bash
# 基础启动
docker compose up -d --build

# 或带生产限制
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 查看日志
docker compose logs -f

# 等待所有服务 healthy
docker compose ps
```

---

## 4. 配置 HTTPS 反代（Caddy）

编辑 `/etc/caddy/Caddyfile`：

```caddy
tars.your-domain.com {
    # 反代到 TARS 前端
    reverse_proxy localhost:8080

    # WebSocket 支持
    @ws {
        header Connection *Upgrade*
        header Upgrade websocket
    }
    reverse_proxy @ws localhost:8080

    # 日志
    log {
        output file /var/log/caddy/tars.log
    }
}
```

重载 Caddy：

```bash
caddy fmt --overwrite /etc/caddy/Caddyfile
systemctl reload caddy
```

> Caddy 自动从 Let's Encrypt 获取免费 SSL 证书并续期。

---

## 5. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health
# 预期: {"status":"ok","version":"5.0.3"}

# 前端页面
curl -I https://tars.your-domain.com
# 预期: HTTP/2 200

# API 文档（仅内网）
curl http://localhost:8000/docs
```

首次登录：`admin` / `Admin123!`（登录后立即修改密码）。

---

## 6. 备份

### 数据库备份

```bash
# 定时任务（每天凌晨 3 点）
crontab -e

# 添加:
0 3 * * * docker exec tars-postgres-1 pg_dump -U tars tars > /data/backups/tars_$(date +\%Y\%m\%d).sql
```

### 文件备份

```bash
# 持久化数据都在 Docker volumes 中
docker volume ls | grep tars

# 备份整个 volumes:
tar -czf /data/backups/tars-volumes-$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/deploy_tars-data/_data \
  /var/lib/docker/volumes/deploy_tars-pg-data/_data \
  /var/lib/docker/volumes/deploy_tars-chroma-data/_data
```

---

## 7. 升级

```bash
cd /data/TARS
git pull origin main
git checkout v5.0.x   # 新版本 tag

# 重建并重启
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build

# 数据库迁移（如果有）
docker exec tars-backend-1 python scripts/migrate_v501_metadata.py
```

---

## 8. 监控与日志

```bash
# 实时日志
docker compose -f deploy/docker-compose.yml logs -f --tail=100

# 资源使用
docker stats

# 磁盘
df -h /data
```

---

## 9. 故障排除

| 现象 | 检查 |
|------|------|
| 页面打不开 | `docker compose ps` → 确认前端和 backend 都是 healthy |
| 聊天无响应 | `docker compose logs backend \| grep -i error` → 检查 LLM provider 连接 |
| 搜索不可用 | `docker compose logs searxng` → 确认 SearXNG healthy |
| 向量搜索退化 | `docker compose logs chromadb` → 确认 ChromaDB healthy |
| 数据库连接失败 | `docker compose logs postgres` → 确认 PG 正常运行 |

---

## 10. 安全清单

- [ ] `TARS_JWT_SECRET` 已改为随机值
- [ ] `PG_PASSWORD` 已改为强密码
- [ ] 管理员密码已修改（默认 `Admin123!`）
- [ ] 安全组只开放 22 / 80 / 443
- [ ] 后端 8000 端口未对外开放
- [ ] API 文档 (`/docs`) 仅限内网访问
- [ ] Caddy HTTPS 已配置且证书正常
- [ ] 备份脚本已添加到 crontab
