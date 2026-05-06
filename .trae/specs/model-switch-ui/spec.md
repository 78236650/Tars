# 模型切换 UI 重构规范

## Why
当前侧边栏模型切换使用两个独立下拉框，逻辑混乱且切换后需要刷新页面才能生效，用户体验差。

## What Changes
- 重构 Sidebar.vue 模型切换区域为 Tab + 列表布局
- 实现点击模型直接切换功能
- 添加切换成功/失败的 Toast 提示
- 确保 ChatView 和 ModelSettings 状态同步

## Impact
- Affected specs: 无
- Affected code:
  - frontend/src/components/layout/Sidebar.vue
  - frontend/src/stores/settings.ts
  - frontend/src/views/ChatView.vue
  - frontend/src/views/ModelSettings.vue

## ADDED Requirements

### Requirement: Tab 切换供应商视图
系统 SHALL 提供 Tab 切换功能，让用户在不同供应商的模型之间切换。

#### Scenario: 切换 Tab
- **WHEN** 用户点击 "Ollama" / "自定义模型" / "OpenRouter" Tab
- **THEN** 显示对应供应商的模型列表

### Requirement: 模型列表展示
系统 SHALL 在每个 Tab 下展示该供应商的所有可用模型。

#### Scenario: 查看模型列表
- **WHEN** 用户选择某个 Tab
- **THEN** 显示该供应商的所有模型列表

### Requirement: 点击直接切换模型
系统 SHALL 支持点击模型直接切换，无需确认按钮。

#### Scenario: 切换模型
- **WHEN** 用户点击模型列表中的某个模型
- **THEN** 调用切换 API，成功后更新当前模型显示

### Requirement: 当前模型视觉标记
系统 SHALL 用绿色边框标记当前使用的模型。

#### Scenario: 识别当前模型
- **WHEN** 用户查看模型列表
- **THEN** 当前使用的模型显示绿色左边框 (border-l-4 border-green-500)

### Requirement: 切换反馈提示
系统 SHALL 在切换成功或失败时显示 Toast 提示。

#### Scenario: 切换成功
- **WHEN** 模型切换 API 返回成功
- **THEN** 显示绿色 Toast："已切换到 xxx"

#### Scenario: 切换失败
- **WHEN** 模型切换 API 返回失败
- **THEN** 显示红色 Toast：显示错误信息

### Requirement: 添加自定义模型入口
系统 SHALL 在"自定义模型"Tab 底部提供添加按钮。

#### Scenario: 添加入口
- **WHEN** 用户在"自定义模型"Tab 下
- **THEN** 显示 "+ 添加自定义模型" 按钮，点击跳转 /models 页面

## MODIFIED Requirements

### Requirement: 模型状态同步
**Modified**: 切换模型后，settingsStore 和 ChatView 应同步更新显示。

#### Scenario: 状态同步
- **WHEN** 用户成功切换模型
- **THEN** settingsStore.currentModel 和 currentProvider 更新，ChatView 顶部显示同步更新

### Requirement: 模型设置页面联动
**Modified**: ModelSettings.vue 中的模型应与 Sidebar 保持一致的切换逻辑。

#### Scenario: 设置页面切换
- **WHEN** 用户在 ModelSettings 页面点击"使用"按钮
- **THEN** 调用相同的切换 API，状态同步更新

## REMOVED Requirements

### Requirement: 下拉框切换
**Reason**: 替换为 Tab + 列表布局，提供更直观的用户体验
**Migration**: 无需迁移，旧功能完全移除

---

## 验收标准

### Sidebar 模型切换
- [ ] Tab 栏正常显示（Ollama、自定义模型、OpenRouter）
- [ ] 点击 Tab 切换视图
- [ ] 模型列表正常显示
- [ ] 当前模型有绿色边框标记
- [ ] 点击模型直接切换
- [ ] 切换成功显示 Toast
- [ ] 切换失败显示错误 Toast
- [ ] 添加自定义模型按钮跳转 /models

### 状态同步
- [ ] settingsStore.currentModel 正确更新
- [ ] settingsStore.currentProvider 正确更新
- [ ] ChatView 顶部显示当前模型
- [ ] 刷新页面后状态保持

### ModelSettings 联动
- [ ] "使用"按钮调用切换 API
- [ ] 切换后状态同步更新
- [ ] 与 Sidebar 显示一致

### 错误处理
- [ ] API 调用失败显示错误 Toast
- [ ] 网络超时显示超时提示
- [ ] 模型连接失败时显示具体错误
