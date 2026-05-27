---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Model Config 页面重设计

## 核心决策

1. **两大类 Provider**：Ollama（本地）+ OpenAI 兼容（统一管理所有远程 API）
2. **端点 + 模型列表**：先配置端点（base_url + key），再拉取/手动添加模型
3. **单页双区块布局**：上 Ollama，下 OpenAI 兼容端点卡片
4. **侧边栏无 tab 分组**：按端点分组展示所有模型，点击即切换

## 数据模型

### 去掉

- `ProviderType` 枚举（OLLAMA/OPENROUTER/ANTHROPIC/OPENAI）
- `CustomModel` 表和相关 CRUD
- `ProviderConfig` 内存存储

### 新增 Endpoint 表（替代 CustomModel）

```
Endpoint:
  id: str (uuid)
  name: str              # 显示名，如 "DeepSeek API"
  base_url: str          # 如 https://api.deepseek.com/v1
  api_key: str           # 可选，加密存储
  models: list[str]      # 该端点下可用模型列表
  enabled: bool
  created_at: datetime
  updated_at: datetime
```

### 当前选中状态

```
provider: "ollama" | "openai_compatible"
endpoint_id: str | null    # openai_compatible 时必填
model: str                 # 具体模型名
```

持久化方式：前端 localStorage + 后端启动时从 localStorage 恢复（通过首次 API 调用传入）。

## 配置页布局

### 区块 1：Ollama 本地模型

- 顶部行：连接状态指示（绿/红点）+ 地址显示（从环境变量读取，不可编辑）
- 模型网格：chip/tag 形式，当前选中高亮，点击切换
- 空状态：提示 `ollama pull <model>`

### 区块 2：OpenAI 兼容端点

- 端点卡片列表，每张卡片：
  - 头部：名称 + base_url
  - 模型 chips：点击切换，当前高亮
  - 操作：拉取模型 / 测试连接 / 编辑 / 删除
- 底部 [+ 添加端点] 按钮
- 添加表单字段：name / base_url / api_key
- 添加后自动调用 `/models` 拉取模型列表，失败则允许手动输入

## 侧边栏快捷切换

Popover 结构（无 tab）：

```
┌─────────────────────┐
│ 本地模型             │
│  ● llama3.2    ✓    │
│  ○ qwen2.5         │
├─────────────────────┤
│ DeepSeek API        │
│  ○ deepseek-chat   │
│  ○ deepseek-coder  │
├─────────────────────┤
│ 内网 vLLM           │
│  ○ qwen-72b       │
├─────────────────────┤
│ ⚙ 模型配置          │
└─────────────────────┘
```

- Ollama 模型在最上面，下面按端点分组
- 点击模型名直接调用 switch API
- 当前模型 ✓ 标记
- 底部跳转配置页

## 后端 API

### 新增

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/models/endpoints` | GET | 获取所有端点（含 models 列表） |
| `/api/models/endpoints` | POST | 创建端点 |
| `/api/models/endpoints/{id}` | PUT | 更新端点 |
| `/api/models/endpoints/{id}` | DELETE | 删除端点 |
| `/api/models/endpoints/{id}/fetch-models` | POST | 拉取端点模型列表 |
| `/api/models/endpoints/{id}/test` | POST | 测试端点连接 |

### 修改

| 端点 | 变更 |
|------|------|
| `POST /api/models/switch` | 统一接口，body: `{provider, endpoint_id?, model}` |
| `GET /api/models/` | 返回 `{ollama_models, endpoints, current: {provider, endpoint_id, model}}` |

### 删除

- `/api/models/providers/*`
- `/api/models/custom/*`
- `/api/models/switch-custom/*`

## 热切换机制

1. 前端点击模型 → `POST /api/models/switch {provider, endpoint_id?, model}`
2. 后端根据 provider 类型：
   - ollama: 实例化 OllamaProvider，设置 model
   - openai_compatible: 从 Endpoint 表读取 base_url/api_key，实例化 CustomProvider
3. 更新 Agent.provider + Agent.current_model
4. 同步 ToolDispatcher 和 MemoryManager
5. 前端 store 更新，localStorage 持久化

## 前端文件变更

| 文件 | 操作 |
|------|------|
| `views/ModelsView.vue` | 重写为新布局 |
| `components/settings/ModelSettings.vue` | 删除（合并到 ModelsView） |
| `components/layout/Sidebar.vue` | 重写模型 popover 部分 |
| `stores/settings.ts` | 重构：endpoint 概念替代 customModels |
| `api/index.ts` | 更新 modelApi 接口 |
| `types/index.ts` | 新增 Endpoint 类型 |

## 后端文件变更

| 文件 | 操作 |
|------|------|
| `models/config.py` | 重写路由，去掉 provider 枚举 |
| `database/custom_model.py` | 重命名为 `database/endpoint.py`，更新 schema |
| `models/custom.py` | 保留，作为 OpenAI 兼容 provider 实现 |
| `models/openrouter.py` | 删除（统一用 custom.py） |
| `agent/agent.py` | 简化 switch 逻辑 |
