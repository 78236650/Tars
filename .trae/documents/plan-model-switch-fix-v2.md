# 模型切换失效问题修复计划

## 问题分析

### 当前流程
```
前端 Sidebar → settingsStore.switchCustomModel() → POST /api/models/switch-custom/{id}
     ↓
后端 switch_to_custom_model() → agent.switch_to_custom_model()
     ↓
agent.provider = CustomProvider(base_url, model, api_key)
     ↓
WebSocket 消息 → agent.handle_message() → self.provider.chat()
```

### 可能的问题点

1. **CustomProvider 初始化问题**：`httpx.AsyncClient` 在 stream 模式下可能没有正确处理
2. **API 地址配置问题**：用户配置的 base_url 可能不正确
3. **HTTP 错误未捕获**：`raise_for_status()` 会抛出异常但没有详细日志
4. **异常被静默吞掉**：`switch_to_custom_model` 中的异常可能被捕获但没有详细信息

## 修复方案

### 1. 修复 CustomProvider 错误处理
**文件**: `backend/tars/models/custom.py`

- 添加更详细的异常日志
- 改进 HTTP 错误处理
- 添加请求/响应日志

### 2. 增强后端 API 错误信息
**文件**: `backend/tars/models/config.py`

- 捕获并记录 CustomProvider 抛出的详细异常
- 返回更友好的错误信息到前端

### 3. 添加模型配置验证
**文件**: `backend/tars/models/config.py`

- 在 `switch_to_custom_model` 中添加模型配置的预检验
- 验证 base_url 格式是否正确

### 4. 前端增强错误显示
**文件**: `frontend/src/composables/useToast.ts`

- 确保错误信息正确显示

## 具体修改

### custom.py 修改
```python
# 1. 添加更详细的异常捕获
async def chat(...):
    try:
        # ...现有逻辑...
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误: {e.response.status_code} - {e.response.text}")
        raise
    except httpx.RequestError as e:
        logger.error(f"请求错误: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Chat 调用异常: {str(e)}")
        raise
```

### config.py 修改
```python
@router.post("/switch-custom/{model_id}")
async def switch_to_custom_model(model_id: str):
    # 添加预检验
    # 验证 base_url 格式
    # 增强错误日志
```

## 验证步骤

1. 重启后端服务
2. 在 Models 设置页面测试"连接"
3. 查看后端日志中的详细错误信息
4. 确认 base_url 格式正确（如 `https://dashscope.aliyuncs.com/compatible-mode/v1`）

## 假设前提

- 用户已重启后端服务
- base_url 配置为完整路径（含 /v1）
- API Key 正确
