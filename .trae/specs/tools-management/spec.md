# Tools 管理页面规范

## Why
TARS Agent 需要一个统一的工具/技能管理中心，让用户可以方便地查看和管理所有内置工具和用户技能。

## What Changes
- 新增 `/tools` 路由和 ToolsView 页面
- 创建技能卡片网格展示
- 实现技能详情弹窗
- 实现添加工具功能（文件导入 + 模板创建）
- 支持技能启用/禁用、配置、重置、删除
- 与 Sidebar 导航集成

## Impact
- Affected specs: Models 页面、Settings 页面
- Affected code: 
  - frontend/src/views/ToolsView.vue
  - frontend/src/components/tools/ToolCard.vue
  - frontend/src/components/tools/ToolDetailModal.vue
  - frontend/src/components/tools/AddToolModal.vue
  - backend/tars/api/tools.py
  - backend/tars/main.py

## ADDED Requirements

### Requirement: 技能列表展示
系统 SHALL 提供卡片网格展示所有工具，支持筛选和搜索。

#### Scenario: 查看技能列表
- **WHEN** 用户访问 /tools 页面
- **THEN** 显示所有内置工具和用户技能，按网格布局展示

### Requirement: 技能详情查看
系统 SHALL 提供弹窗展示技能详情。

#### Scenario: 查看详情
- **WHEN** 用户点击技能卡片
- **THEN** 显示技能介绍、使用方法、配置参数

### Requirement: 技能管理
系统 SHALL 提供启用/禁用、配置、删除功能。

#### Scenario: 管理技能
- **WHEN** 用户在详情弹窗中操作
- **THEN** 支持启用/禁用、重置配置、删除用户技能

### Requirement: 添加技能
系统 SHALL 支持文件导入和模板创建。

#### Scenario: 添加新技能
- **WHEN** 用户点击添加技能按钮
- **THEN** 显示文件上传和模板选择界面

## MODIFIED Requirements

### Requirement: Sidebar 导航
**Modified**: 添加 Tools 导航入口
- **WHEN** 用户点击 Sidebar 中的 Tools
- **THEN** 导航到 /tools 页面

## REMOVED Requirements
无

---

## 验收标准

### 前端功能
- [ ] /tools 页面正确渲染
- [ ] 技能卡片网格正确显示
- [ ] 筛选功能正常工作（全部/内置/用户/已禁用）
- [ ] 搜索功能正常工作
- [ ] 详情弹窗正确显示
- [ ] 添加技能弹窗正确显示
- [ ] 启用/禁用开关正常工作
- [ ] 配置编辑保存成功
- [ ] 重置配置功能正常
- [ ] 删除用户技能正常（内置不可删除）
- [ ] 文件导入功能正常
- [ ] 模板创建功能正常
- [ ] 返回按钮正常工作

### 后端功能
- [ ] GET /api/tools 返回所有工具列表
- [ ] GET /api/tools/{id} 返回工具详情
- [ ] PUT /api/tools/{id}/config 更新配置
- [ ] PUT /api/tools/{id}/status 更新状态
- [ ] POST /api/tools 添加工具
- [ ] DELETE /api/tools/{id} 删除工具
- [ ] GET /api/tools/templates 返回模板列表

### UI/UX
- [ ] 页面布局与 Models/Settings 风格一致
- [ ] 弹窗样式统一
- [ ] 响应式适配
