# 部署指南

## 环境要求

### 系统要求
- Python 3.11+
- Node.js 18+
- 操作系统：macOS / Linux / Windows (WSL2)

### 资源要求
- 内存：2GB+ (推荐 4GB+)
- 存储：500MB+

---

## 本地开发部署

### 1. 克隆代码

```bash
git clone <repo-url>
cd TARS
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 .\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 前端设置

```bash
cd ../frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

### 4. 启动服务

```bash
# 后端（在 backend/ 目录下）
source venv/bin/activate
python -m tars.main

# 前端（在 frontend/ 目录下）
npm run dev
```

访问 `http://localhost:5173` 即可使用。

---

## 配置

### 环境变量

```bash
# .env
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# 默认配置
TARS_DATA_DIR=~/.tars
TARS_HOST=0.0.0.0
TARS_PORT=8000
```

### 配置文件

`~/.tars/config.yaml`

```yaml
model:
  provider: openrouter
  model: anthropic/claude-sonnet-4
  context_length: 128000
  temperature: 0.7

providers:
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
  ollama:
    base_url: "http://localhost:11434"

security:
  dangerous_commands:
    - rm -rf
    - mkfs
    - dd if=
  allowed_paths:
    - ~/.tars
    - ~/projects
  blocked_paths:
    - /etc
    - /var
    - /root

rate_limit:
  requests_per_minute: 30
  max_tokens_per_request: 8000
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
      - ~/.tars:/root/.tars
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

  frontend:
    build:
      context: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

### 启动

```bash
docker-compose up -d
```

---

## 桌面端 (Tauri)

### 开发模式

```bash
cd frontend
npm run tauri dev
```

### 打包

```bash
npm run tauri build
```

---

## 备份

```bash
# 备份数据目录
tar -czf tars-backup-$(date +%Y%m%d).tar.gz ~/.tars
```

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
