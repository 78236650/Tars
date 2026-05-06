# Tasks - Tools 管理页面实现

## 任务列表

### Phase 1: 后端 API
- [x] Task 1.1: 创建 backend/tars/api/tools.py ✅
  - 实现 GET /api/tools 获取工具列表
  - 实现 GET /api/tools/{id} 获取详情
  - 实现 PUT /api/tools/{id}/config 更新配置
  - 实现 PUT /api/tools/{id}/status 更新状态
  - 实现 POST /api/tools 添加工具
  - 实现 DELETE /api/tools/{id} 删除工具
  - 实现 GET /api/tools/templates 获取模板列表
  - 集成现有 tool_registry

### Phase 2: 前端页面
- [x] Task 2.1: 创建 frontend/src/views/ToolsView.vue ✅
  - 主页面布局
  - Header 和返回按钮
  - 筛选和搜索功能

- [x] Task 2.2: 创建 frontend/src/components/tools/ToolCard.vue ✅
  - 技能卡片组件
  - 图标、名称、状态显示
  - 快捷操作按钮

- [x] Task 2.3: 创建 frontend/src/components/tools/ToolDetailModal.vue ✅
  - 详情弹窗组件
  - 介绍和使用方法展示
  - 配置参数编辑
  - 启用/禁用、重置、删除按钮

- [x] Task 2.4: 创建 frontend/src/components/tools/AddToolModal.vue ✅
  - 添加技能弹窗
  - 文件导入功能
  - 模板选择功能

### Phase 3: 路由和导航
- [x] Task 3.1: 更新 frontend/src/router/index.ts ✅
  - 添加 /tools 路由
  - 关联 ToolsView 组件

- [x] Task 3.2: 更新 frontend/src/components/layout/Sidebar.vue ✅
  - 添加 Tools 导航入口

### Phase 4: 后端路由注册
- [x] Task 4.1: 更新 backend/tars/main.py ✅
  - 导入 tools API 路由
  - 注册路由到应用

## 任务依赖
- Task 2.1-2.4 可以在 Task 1.1 完成后并行开发
- Task 3.1-3.2 依赖 Task 2.1 完成
- Task 4.1 依赖 Task 1.1 完成
