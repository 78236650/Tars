# 模型切换功能全面修复计划

## 问题分析

用户反馈：配置了阿里云的 qwen3.6-plus 模型，但聊天仍使用本地 Ollama 模型。

### 问题根源

#### 1. 后端 `switch_to_custom_model()` API 返回问题
- **文件**: `backend/tars/models/config.py`
- **问题**: 返回的 `current_model` 使用的是传入的 `model.model`，而非 agent 实际设置后的值
- **问题**: `_current_provider` 更新在返回之前可能有时序问题

#### 2. 前端 `switchCustomModel` 缺少错误处理
- **文件**: `frontend/src/stores/settings.ts`
- **问题**: 没有处理非 200 响应，也没有显示错误信息

#### 3. 前端切换后 WebSocket 未重连
- **问题**: 切换模型后，WebSocket 连接可能仍在使用旧的 provider 实例
- **解决**: 切换模型后应重连 WebSocket

#### 4. 缺少调试日志
- 后端缺少切换模型的日志
- 无法追踪切换是否真正成功

## 修复方案

### Step 1: 修复后端 `switch_to_custom_model` 返回值

**文件**: `backend/tars/models/config.py`

修改 `switch_to_custom_model` 函数：
```python
# 更新 _current_provider 在调用 agent 方法之前
_current_provider = f"custom:{model_id}"

agent = get_agent()
success = agent.switch_to_custom_model(...)

return {
    "success": True,
    "message": f"已切换到自定义模型: {model.name}",
    "current_model": agent.current_model,  # 使用 agent 实际设置的值
    "current_provider": _current_provider
}
```

### Step 2: 添加后端日志

**文件**: `backend/tars/models/config.py`

在 `switch_to_custom_model` 中添加日志：
```python
import logging
logger = logging.getLogger(__name__)

# 在方法中添加
logger.info(f"切换到自定义模型: {model.name}, model={model.model}, base_url={model.base_url}")
```

### Step 3: 修复前端 `switchCustomModel`

**文件**: `frontend/src/stores/settings.ts`

```typescript
const switchCustomModel = async (modelId: string) => {
  loading.value = true
  try {
    const response = await fetch(`/api/models/switch-custom/${modelId}`, {
      method: 'POST'
    })
    const data = await response.json()

    if (data.success) {
      currentModel.value = data.current_model
      currentProvider.value = data.current_provider
      return { success: true, message: data.message }
    } else {
      return { success: false, message: data.detail || '切换失败' }
    }
  } catch (error) {
    return { success: false, message: '网络错误' }
  } finally {
    loading.value = false
  }
}
```

### Step 4: 切换模型后重连 WebSocket

**文件**: `frontend/src/components/layout/Sidebar.vue`

```typescript
const switchToCustomModel = async (model: any) => {
  const result = await settingsStore.switchCustomModel(model.id)
  if (result.success) {
    // 重新加载模型列表确保同步
    await settingsStore.loadModels()
    // 提示用户刷新页面或自动重连
    alert('模型切换成功，请刷新页面以使用新模型')
  } else {
    alert('切换失败: ' + result.message)
  }
}
```

### Step 5: ChatView 切换后提示用户

**文件**: `frontend/src/views/ChatView.vue`

添加一个响应式提示：
```typescript
const modelJustSwitched = ref(false)

// 在切换后设置标志
watch(() => settingsStore.currentModel, (newModel, oldModel) => {
  if (newModel !== oldModel && oldModel !== '') {
    modelJustSwitched.value = true
    setTimeout(() => { modelJustSwitched.value = false }, 5000)
  }
})
```

## 涉及文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/tars/models/config.py` | 修复返回值顺序，添加日志 |
| `frontend/src/stores/settings.ts` | 改进错误处理，返回详细信息 |
| `frontend/src/components/layout/Sidebar.vue` | 切换后提示 |
| `frontend/src/views/ChatView.vue` | 显示切换提示 |

## 验证步骤

1. 启动后端 `uvicorn main:app --reload`
2. 检查后端日志，确认切换时有日志输出
3. 在前端切换到自定义模型
4. 确认 API 响应中 `success: true`
5. 刷新页面
6. 发送测试消息，确认使用的是新模型
7. 检查 WebSocket 消息中的 `model` 字段
