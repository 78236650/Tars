---
doc_type: spec
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# 模型切换 UI 重构设计方案

## 概述

将侧边栏模型切换区域从当前的两个独立下拉框改为 Tab 切换 + 模型列表布局，提供更直观的模型选择体验。

## 当前问题分析

### UI 问题
- 两个下拉框逻辑混乱（自定义模型和 Ollama 模型是平级关系，但 UI 没有体现）
- 切换后需要刷新页面才能生效，用户体验差
- 没有清晰展示当前使用的模型

### 功能问题
- 切换 API 调用后没有实时反馈
- 供应商和模型的关系不清晰
- 自定义模型和 Ollama 模型可能存在命名冲突

## 影响范围分析

### 前端影响
1. **Sidebar.vue** - 主模型切换区域重构
2. **settings.ts (Pinia Store)** - 可能需要调整状态管理
3. **ChatView.vue** - 顶部显示当前模型，可能需要同步刷新
4. **ModelSettings.vue** - 设置页面的模型管理可能需要联动

### 后端影响
1. **models/config.py** - API 端点已完善，无需修改
2. **agent/base.py** - 模型切换逻辑已完善
3. **models/custom.py** - 刚修复 `/v1` 路径问题

### 数据流影响
```
用户点击模型
    ↓
前端 API 调用 (POST /api/models/switch-custom/{id} 或 /api/models/switch)
    ↓
后端 Agent 切换 Provider
    ↓
WebSocket 推送更新事件（可选）
    ↓
前端刷新当前模型显示
    ↓
ChatView 自动使用新模型
```

## 设计方案

### 布局结构

```
┌─────────────────────────────────────────────────────┐
│  🤖 当前模型                                         │
│  qwen3.6-plus                                       │
│  <span class="provider-badge">自定义模型</span>      │
├─────────────────────────────────────────────────────┤
│  [Ollama]  [自定义模型]  [OpenRouter]              │  ← Tab 栏
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐   │
│  │ ● qwen3:8b                               →  │   │  ← 选中样式
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │   qwen2.5:14b                            →  │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │   gemma4:e2b                              →  │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  （自定义模型 Tab 下）                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ ● qwen3.6-plus (qwen3.6-plus)            →  │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │   DeepSeek V3 (deepseek-chat)             →  │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  [+ 添加自定义模型]                                 │  ← 添加入口
└─────────────────────────────────────────────────────┘
```

### 组件状态

| 状态 | 样式 |
|------|------|
| 默认 | 背景 slate-700，白色文字 |
| 当前使用 | 左边框绿色 (border-l-4 border-green-500)，背景略浅 |
| 悬停 | 背景变亮 (hover:bg-slate-600) |

### 交互逻辑

1. **Tab 切换**：点击 Tab 切换供应商视图，Tab 显示该供应商的模型列表
2. **模型选择**：点击模型直接切换，无需确认按钮
3. **视觉反馈**：
   - 当前使用的模型有绿色左边框
   - 切换成功：短暂显示成功提示（2秒 toast）
   - 切换失败：显示错误提示
4. **添加按钮**：点击跳转 Models 页面添加新模型

### 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| API 调用失败 | Toast 显示错误信息，模型列表不变 |
| 模型连接超时 | Toast 显示 "连接超时，请检查网络" |
| 切换后模型无响应 | 自动回退到上一个可用模型 |

## 页面联动

### 涉及的页面和组件

1. **Sidebar.vue** - 主切换区域（本次修改重点）
2. **ChatView.vue** - 顶部显示当前模型，需要同步更新
3. **ModelSettings.vue** - Models 设置页面，需要保持 UI 一致性

### 状态同步

- `settingsStore.currentModel` - 当前模型名称
- `settingsStore.currentProvider` - 当前供应商类型
- 切换成功后自动更新这两个状态
- ChatView 通过 watch 监听变化，自动更新显示

## API 接口（已实现）

### 切换自定义模型
```
POST /api/models/switch-custom/{model_id}
Response: {
  success: boolean,
  message: string,
  current_model: string,
  current_provider: string
}
```

### 切换 Ollama 模型
```
POST /api/models/switch
Body: { model_name: string, provider?: "ollama" }
Response: { success, message, current_model, current_provider }
```

### 获取模型列表
```
GET /api/models
Response: {
  models: string[],
  current_model: string,
  current_provider: string
}

GET /api/models/custom
Response: CustomModel[]
```

## 实现计划

### 阶段一：Sidebar 重构
1. 替换当前下拉框为 Tab + 列表布局
2. 添加切换动画
3. 添加成功/失败 toast 提示

### 阶段二：状态同步
1. 确保 settingsStore 状态正确更新
2. ChatView 顶部显示同步更新
3. 刷新页面后保持状态

### 阶段三：ModelSettings 联动
1. 检查 Models 页面的模型切换逻辑
2. 确保两处 UI 一致性
3. 添加"使用此模型"按钮

## 测试要点

1. ✅ Tab 切换正常切换视图
2. ✅ 点击模型立即切换
3. ✅ 切换成功显示 toast
4. ✅ 切换失败显示错误
5. ✅ 当前模型有视觉标记
6. ✅ 刷新页面后状态保持
7. ✅ ChatView 显示正确模型
8. ✅ ModelSettings 和 Sidebar 状态一致
