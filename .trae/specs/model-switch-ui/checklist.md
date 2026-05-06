# 检查清单

## Sidebar 重构
- [x] Tab 栏正确渲染（Ollama、自定义模型、OpenRouter）
- [x] 点击 Tab 切换视图功能正常
- [x] 模型列表正确显示
- [x] 当前模型有绿色左边框标记
- [x] 模型点击直接切换功能正常
- [x] 切换成功显示绿色 Toast
- [x] 切换失败显示红色 Toast
- [x] "添加自定义模型"按钮存在且可点击跳转

## 状态同步
- [x] settingsStore.currentModel 在切换后正确更新
- [x] settingsStore.currentProvider 在切换后正确更新
- [x] ChatView 顶部显示当前模型
- [x] 刷新页面后状态保持

## ModelSettings 联动
- [x] "使用"按钮正确调用切换 API
- [x] 切换后状态与 Sidebar 同步
- [x] UI 样式与 Sidebar 一致

## 错误处理
- [x] API 调用失败时显示错误 Toast
- [x] 网络错误显示友好提示
- [x] 切换超时处理正确

## 代码质量
- [x] 无 console.error（代码中已检查）
- [x] 无未处理的 Promise rejection
- [x] TypeScript 类型正确
- [x] 代码风格一致
- [x] Vite 构建成功
