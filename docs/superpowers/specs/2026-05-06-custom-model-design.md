# 自定义模型配置功能集成设计

## 目标
完善自定义模型配置功能，确保所有功能点都能正确使用用户选择的模型。

## 当前状态

### 已实现
- ✅ CustomProvider - OpenAI 兼容 API 调用
- ✅ CustomModelStore - 数据库 CRUD
- ✅ API 端点 - CRUD + switch-custom
- ✅ Agent.switch_to_custom_model() - 模型切换
- ✅ 前端 ModelSettings - 添加/管理自定义模型
- ✅ Sidebar - 显示当前模型和切换

### 待修复
- ❌ 子代理不使用当前模型，始终使用默认 Ollama
- ❌ ModelSettings 未同步当前选中的自定义模型
- ❌ 聊天页面未显示当前使用的模型
- ❌ 切换模型后无成功/失败反馈

## 修复方案

### 1. 子代理支持当前模型

**问题**: `subagent_manager.py` 始终创建新的 OllamaProvider，不使用当前 Agent 的 provider

**修复**:
```python
# subagent_manager.py
async def invoke_subagent(self, agent_type: str, task: str, context: dict):
    # 使用当前 Agent 的 provider，而非创建新的
    subagent = self.get_subagent(agent_type)
    # 直接使用 self.agent.provider 而不是创建新的
    response = await self.agent.provider.chat(messages, stream=False)
```

### 2. 前端同步当前模型状态

**问题**: ModelSettings 未显示当前选中的模型

**修复**:
- 加载时从 `/api/models` 获取 current_provider
- 区分显示 Ollama 模型和自定义模型
- 当前选中的模型高亮显示

### 3. 聊天页面显示当前模型

**问题**: 用户不知道当前使用哪个模型

**修复**:
- 在 ChatView header 显示当前模型名称
- 响应式更新，切换后自动刷新

### 4. 切换成功/失败反馈

**问题**: 切换后无反馈，用户不确定是否成功

**修复**:
- 使用前端 Toast/Notification 组件
- 切换成功显示绿色提示
- 切换失败显示红色提示 + 错误原因

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/models` | GET | 获取当前模型和 provider |
| `/api/models/custom` | GET/POST | 自定义模型 CRUD |
| `/api/models/switch-custom/{id}` | POST | 切换到自定义模型 |

## 数据流

```
用户选择模型
    ↓
前端调用 /api/models/switch-custom/{id}
    ↓
Agent.switch_to_custom_model()
    ↓
更新 agent.provider → CustomProvider
    ↓
所有后续聊天使用新模型
```

## 组件修改

### 后端
- `agent/subagent_manager.py` - 使用当前 provider
- `agent/base.py` - 确保 provider 正确传递

### 前端
- `stores/settings.ts` - 添加 Toast 状态
- `views/ChatView.vue` - 显示当前模型
- `components/settings/ModelSettings.vue` - 同步当前模型
- `components/layout/Sidebar.vue` - 已完成

## 实现步骤
1. 修复子代理使用当前 provider
2. 完善 ModelSettings 当前模型显示
3. ChatView 显示当前模型
4. 添加切换成功/失败反馈
