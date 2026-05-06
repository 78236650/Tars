# 项目概览

## TARS 是什么？

TARS 是一个高度自主、可配置的 AI Agent，灵感来自电影《星际穿越》中的机器人 TARS。它具有以下核心特性：

- 🎭 **可调人格** - honesty、humor、initiative、empathy 四个参数实时调节
- 🧠 **三层记忆 V3（Letta 混合模式）** - Core Memory（4 块固定区块：persona / user_profile / project_context / working_principles）注入 system prompt + Archival Memory（embedding 检索 + Ebbinghaus 衰减）+ Reflector 反思器异步沉淀
- 🔌 **可扩展工具** - 7 个核心工具 + 技能生态系统
- 🔀 **模型无关** - 统一 Provider 接口，支持 OpenRouter、Anthropic、OpenAI、Ollama
- 🌐 **多通道支持** - Web、Telegram、飞书、Webhook
- ⚡ **流式响应** - 实时交互体验

## 快速导航

| 文档 | 说明 |
|------|------|
| [系统全景图](../02-技术方案/architecture/system-overview.md) | 整体架构、核心特性、技术栈 |
| [分层详细设计](../02-技术方案/architecture/layer-design.md) | 各层详细设计图 |
| [数据流图](../02-技术方案/architecture/data-flow.md) | 完整消息处理流程 |
| [WebSocket 协议](../02-技术方案/api/websocket-protocol.md) | 前后端通信协议 |
| [组件关系图](../02-技术方案/architecture/component-relation.md) | 组件依赖关系 |
| [数据库设计](../02-技术方案/database/schema.md) | SQLite Schema |
| [项目路线图](../03-实施计划/roadmap.md) | 实施计划和里程碑 |
| [部署指南](../04-运维文档/deployment.md) | 如何部署 TARS |

## 设计理念

TARS 的设计融合了两个优秀开源项目的思想：

- **OpenClaw** - 五层架构和工作区文件系统
- **Hermes Agent** - 工具注册表和技能生态系统

在此基础上，我们加入了来自《星际穿越》的设计灵感：

- 可调人格参数
- 可靠、幽默的交互风格
- 高度自主的执行能力

## 技术栈

### 后端
- **FastAPI** - Web 框架
- **Python 3.11+**
- **SQLite + FTS5** - 数据库和全文检索
- **asyncio** - 异步编程

### 前端
- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **TailwindCSS** - 样式
- **Zustand** - 状态管理

### 模型支持
- OpenRouter (默认)
- Anthropic Claude
- OpenAI GPT
- Ollama (本地)

## 项目状态

- **当前阶段**: 设计阶段 ✅
- **下一步**: Phase 1 - 项目骨架

## 相关链接

- [DESIGN.md](../../DESIGN.md) - 完整架构设计方案
- [GitHub (待创建)]()
- [问题反馈 (待创建)]()

---

*文档版本: v1.0*  
*创建日期: 2026-05-05*
