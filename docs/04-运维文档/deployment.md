# TARS 部署指南

## 环境要求

### 系统要求
- Python 3.11+
- Node.js 18+
- 操作系统：macOS / Linux / Windows (WSL2)
- Ollama（本地模型，推荐）

### 资源要求
- 内存：4GB+（Ollama 模型需额外显存/内存）
- 存储：1GB+

---

## 快速部署

### 1. 克隆代码

```bash
git clone <repo-url>
cd TARS
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，按需填入 API Key
```

### 3. 前端设置

```bash
cd ../frontend
npm install
```

### 4. 启动

```bash
# 后端
cd backend
.venv/bin/python -m uvicorn tars.main:app --host 0.0.0.0 --port 8000

# 前端（另一个终端）
cd frontend
npm run dev
```

访问 `http://localhost:5173`。

---

## 配置文件（v4.0.0）

TARS v4.0.0 使用 YAML 配置文件，位于 `backend/config/`：

### providers.yaml — LLM Provider 配置

```yaml
default_provider: ollama-local

providers:
  ollama-local:
    type: ollama
    base_url: http://localhost:11434
    default_model: qwen3:8b
    display_name: Ollama (本地)

  # 示例：DeepSeek
  # deepseek:
  #   type: openai_compat
  #   base_url: https://api.deepseek.com/v1
  #   api_key: "${DEEPSEEK_API_KEY}"
  #   default_model: deepseek-chat
```

环境变量用 `${VAR_NAME}` 引用，启动时自动展开。

### modules.yaml — 模块启用/禁用

```yaml
modules:
  core:
    - agent
    - tools
    - skills
    - memory
    - auth
    - security

  optional:
    meeting:
      enabled: false        # 需要 whisper 模型
    bi:
      enabled: false        # 需要 pandas
    knowledge:
      enabled: true
    skillhub:
      enabled: true
```

禁用的模块不注册路由，不加载依赖，减少启动时间和内存占用。

### concurrency.yaml — 并发限流

```yaml
providers:
  ollama:
    max_concurrent: 2       # 全局最大并发 LLM 调用
    per_user_max: 1         # 单用户最多占 1 个槽位
    queue_timeout: 60       # 排队超时（秒）
  custom:
    max_concurrent: 5
    per_user_max: 2
    queue_timeout: 30
```

### tool_permissions.yaml — 工具权限

```yaml
roles:
  admin:
    allowed_tools: "*"
  user:
    allowed_tools: [weather, web_search, web_fetch, file, file_write, python_exec, memory, command, knowledge_search]
    denied_tools: [shell, process, network]
  guest:
    allowed_tools: [weather, web_search]
```

---

## 环境变量

在 `backend/.env` 中配置：

```bash
# LLM API Keys（按需配置）
DEEPSEEK_API_KEY=sk-...
DASHSCOPE_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...

# Ollama（默认本地）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# 连接池超时（可选）
TARS_LLM_READ_TIMEOUT=600
TARS_LLM_CONNECT_TIMEOUT=30
```

---

## Docker 部署

### docker-compose.yml

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/config:/app/config
      - tars-data:/app/data
    env_file:
      - ./backend/.env
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  tars-data:
```

### 启动

```bash
docker-compose up -d
```

---

## 多用户部署注意事项

### 默认管理员

首次启动自动创建 admin 账户（用户名 `admin`，密码见启动日志）。建议首次登录后立即修改密码。

### 安全建议

1. **修改默认密码** — 首次部署后立即修改 admin 密码
2. **限制网络访问** — 内网部署建议绑定内网 IP，不暴露公网
3. **配置工具权限** — 根据用户角色调整 `tool_permissions.yaml`
4. **启用审计日志** — 默认已启用，通过 `/api/audit/logs` 查看
5. **定期备份** — 备份 `backend/data/` 目录（含 SQLite 数据库）

### 性能调优

| 场景 | 建议配置 |
|------|---------|
| 2-5 用户 | `max_concurrent: 2`, `per_user_max: 1` |
| 5-20 用户 | `max_concurrent: 4`, `per_user_max: 1`，建议云端 API |
| 20+ 用户 | 多实例部署 + 负载均衡 |

---

## 备份与恢复

```bash
# 备份
tar -czf tars-backup-$(date +%Y%m%d).tar.gz backend/data/ backend/config/

# 恢复
tar -xzf tars-backup-20260517.tar.gz
```

---

## 从 v3.x 升级

```bash
# 1. 拉取最新代码
git pull origin v4.0.0

# 2. 更新依赖
cd backend && pip install -r requirements.txt

# 3. 生成 providers.yaml（从环境变量自动迁移）
python scripts/migrate_providers.py

# 4. 重启服务
```

数据库自动迁移（ALTER TABLE 加 scope 字段等），无需手动操作。

---

*文档版本: v4.0.0 | 更新日期: 2026-05-17*
