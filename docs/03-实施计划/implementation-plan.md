# 详细实施计划

## 资源需求

### 开发环境

- Python 3.11+
- Node.js 18+
- Git
- 代码编辑器（VS Code 推荐）

### 外部依赖

- OpenRouter API Key（或其他 LLM Provider）
- Telegram Bot Token（可选，Phase 1 之后）
- 飞书/钉钉 App（可选，Phase 1 之后）

---

## Phase 1: 骨架 (1-2 天)

### Day 1 - 项目初始化

- [ ] 创建 Git 仓库
- [ ] 后端项目初始化
  - [ ] 创建 `backend/` 目录结构
  - [ ] 配置 `pyproject.toml` 和 `requirements.txt`
  - [ ] 基础 FastAPI app
- [ ] 前端项目初始化
  - [ ] 创建 `frontend/` 目录结构
  - [ ] 使用 Vite 初始化 React + TypeScript 项目
  - [ ] 配置 TailwindCSS、Zustand、React Router

### Day 2 - WebSocket 连接

- [ ] 后端 WebSocket 端点
- [ ] 前端 WebSocket Hook
- [ ] 基础连接测试
- [ ] 简单的 ping/pong 心跳

**里程碑 M1: 项目启动** ✅

---

## Phase 2: 对话 (2-3 天)

### Agent Loop 实现

- [ ] Core Agent Loop
- [ ] System Prompt 构建
- [ ] 会话历史管理

### LLM Provider 抽象

- [ ] Provider ABC 接口
- [ ] OpenRouter Provider 实现
- [ ] 流式响应支持

### 会话管理（SQLite）

- [ ] Sessions 表
- [ ] Messages 表
- [ ] 会话 CRUD 操作

**里程碑 M2: 可对话** ✅

---

## Phase 3: Gateway (1-2 天)

### 身份验证

- [ ] API Key 验证
- [ ] Channel-User 绑定

### 速率限制

- [ ] Token Bucket 算法实现
- [ ] 按用户/IP 限制

### 安全策略

- [ ] 危险命令检测
- [ ] 文件路径白名单/黑名单
- [ ] 操作拦截

**里程碑 M3: 安全通道** ✅

---

## Phase 4: SOUL (1-2 天)

### 工作区文件解析

- [ ] SOUL.md 读写
- [ ] AGENTS.md 读写
- [ ] MEMORY.md 读写
- [ ] USER.md 读写

### 人格参数可视化

- [ ] 参数滑块组件
- [ ] 实时更新 System Prompt

**里程碑 M4: 可调人格** ✅

---

## Phase 5: 记忆 (2-3 天)

### 双层存储

- [ ] MEMORY.md 读写
- [ ] SQLite FTS5 索引

### 自动提取

- [ ] 调用 LLM 提取记忆
- [ ] 自动保存到 MEMORY.md

### 全文检索

- [ ] FTS5 索引创建
- [ ] 相关记忆检索接口

**里程碑 M5: 有记忆** ✅

---

## Phase 6: 工具 (3-4 天)

### 工具注册表

- [ ] ToolRegistry 实现
- [ ] 自动发现机制
- [ ] JSON Schema 生成

### 核心工具实现

- [ ] terminal - 命令执行
- [ ] file - 文件读写搜索
- [ ] browser - 浏览器自动化
- [ ] web - 网络搜索
- [ ] delegate - 子代理
- [ ] cronjob - 定时任务
- [ ] memory - 记忆管理

### 安全隔离

- [ ] 危险命令确认
- [ ] 文件路径检查

**里程碑 M6: 能执行** ✅

---

## Phase 7: 技能 (2-3 天)

### 技能系统

- [ ] SKILL.md 格式定义
- [ ] 技能加载器
- [ ] 技能激活/停用

### 技能市场

- [ ] 技能列表页面
- [ ] 技能安装/卸载

**里程碑 M7: 可扩展** ✅

---

## Phase 8: 完善 (3-4 天)

### 前端功能

- [ ] PWA 支持
- [ ] 工作看板
- [ ] 系统设置页面
- [ ] 深色模式
- [ ] 响应式设计

**里程碑 M8: Web 产品** ✅

---

## Phase 9: 桌面化 (2-3 天)

### Tauri 包装

- [ ] Tauri 项目初始化
- [ ] 系统托盘
- [ ] 文件关联
- [ ] 打包发布

**里程碑 M9: 桌面端** ✅

---

## 风险评估

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|---------|
| LLM API 不稳定 | 高 | 中 | 支持多个 Provider，支持降级 |
| 工具执行安全性 | 高 | 低 | 安全策略 + 用户确认 |
| 前端复杂度 | 中 | 中 | 分阶段实现，优先核心功能 |
| 记忆提取效果 | 中 | 中 | Prompt 调优 + 人工编辑 |

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
