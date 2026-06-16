# TARS v5.0.5/A4 最终能力评估

> 评估日期：2026-06-16 · 基于 17 文件、~940 行增量、48/48 测试全绿

---

## 一、能力热力图

```
                              能力强度                            状态
                              ─────────────────────────────────
记忆写入/Reflector          ██████████ A+   10种op，三层降级           生产
写入去重/增量更新            ██████████ A    四层去重+写入时检查+update  生产
语义检索/HybridSearch       ██████████ A    Chroma+FTS5+decay+rerank 生产
Core Memory                ██████████ A    4块+trim+行去重+用户私有   生产
实体知识图谱                ██████████ A    entities+relations+FTS5   生产
Ebbinghaus 遗忘             ██████████ A    衰减公式+定时cleanup        生产
解决思路学习(log_solution)  ████████░ A-   完整实现，待实战验证         新
步骤记忆(log_procedure)     ████████░ A-   完整实现，待实战验证         新
用户纠正记录(log_correction) ████████░ A-   完整实现，待实战验证         新
Evolution↔Memory 桥梁       ████████░ A-   Analyzer+Bridge+集成       新
实体图关联发现              ████████░ A-   cross_entity_discovery     新
主动记忆提醒                ████████░ A-   proactive_reminders        新
记忆→知识库(KB Promotion)   ████████░ B+   批量LLM合成Markdown         生产
后台维护(SleepAgent)        ████████░ B+   去重+冲突+衰减              生产
Agent 规划(PlanExecutor)    ███████░░ B     轻量prompt增强模式         新
LLM 可观测性                ███████░░ B     4个Prom指标+Admin API      新
子Agent 记忆共享             ███████░░ B     delegate注入记忆上下文      新
主动预警(AlertEngine)       ██████░░░ C+    3种检测+每6小时定时巡检     新
上下文感知(Scene Analyzer)  ███████░░ B     意图识别+Working Context   生产

────────────────────────────
实战验证缺口                  ░░░░░░░░░░░ ?   8项新功能待生产数据验证
```

---

## 二、分层解读

### 🔵 记忆层 (Memory) — A 级，行业领先

| 指标 | 数值 | 对标 |
|------|------|------|
| Reflector op 类型 | 10 种 | Letta: 6种, CrewAI: 4种 |
| 去重层级 | 4 层 + 写入时 | Zep/Mem0: 3层 |
| 检索路径 | 5 条（Chroma/FTS5/SQLite/关键词/确定性向量） | 行业平均: 2-3条 |
| 衰减算法 | Ebbinghaus 公式 | 独有，无对标 |
| 记忆→知识库 | KB Promotion 批量合成 | 独有 |
| 领域 schema | 港航8类实体+6种关系 | 独有 |
| Evolution 闭环 | 已打通 | 独有 |

### 🟢 Agent 层 — B 级，够用但不如记忆突出

| 能力 | 评分 | 说明 |
|------|:---:|------|
| Prompt 工程 | A- | 渐进披露/DONE-BLOCKED-GO/置信度声明，成熟 |
| 工具系统 | B+ | 21个内置工具，调度/校验/沙箱完善 |
| 规划能力 | B | PlanExecutor（新），轻量 prompt 增强，非显式状态机 |
| 子Agent系统 | B | 记忆共享已注入（新），handoff写回待完善 |
| 技能路由 | B+ | SkillRouter 自动匹配+渐进披露 |
| 编排 | B | TaskDetector+港航作业MVP |

### 🟡 运维层 (Observability) — B- 级，有基础但缺深度

| 能力 | 评分 | 说明 |
|------|:---:|------|
| LLM 指标 | B | 4个Prom指标+Admin API（新） |
| 审计 | B+ | 完整的审计日志 |
| 预警 | C+ | AlertEngine 3种检测（新） |
| 分布式追踪 | F | 无 |
| 仪表盘 | C | 前端有基础但无LLM用量看板 |

### 🟠 体验层 (Frontend) — B 级，功能全但体验可打磨

| 能力 | 评分 | 说明 |
|------|:---:|------|
| 对话界面 | B+ | Vue3+SSE+Markdown渲染 |
| 记忆管理 | B+ | 实体树+Tab切换 |
| 知识库 | B+ | Wiki Tab+检索 |
| 数据看板 | C+ | BI/InsightForge有基础 |
| 大数据渲染 | C | 500节点卡顿，待虚拟滚动 |
| 操作向导 | D | 无引导式操作 |

---

## 三、行业对标总表

| 能力 | TARS | Letta | LangGraph | CrewAI | Mem0 |
|------|:---:|:---:|:---:|:---:|:---:|
| 记忆体系 | **A+** | A | C | B+ | B+ |
| Agent 核心 | **B** | B+ | A- | B+ | - |
| 可观测性 | **B-** | C | C | C | B |
| 安全性 | **B+** | C | C | C | B |
| 港航专长 | **A** | - | - | - | - |
| Evolution | **A-** | - | - | - | - |
| **综合** | **A-** | **B+** | **B** | **B** | **B** |

---

## 四、剩余缺口

| 缺口 | 严重度 | 计划 |
|------|:---:|------|
| PlanExecutor 未进化为显式状态机 | 中 | 后续迭代 |
| 子Agent handoff 未写回 Memory | 中 | 后续迭代 |
| 无分布式追踪 | 低 | v5.1+ |
| 前端大数据卡顿 | 中 | 迭代三 |
| 新功能未实战验证 | 高 | 生产环境运行 2 周后复盘 |

---

*TARS v5.0.5/A4 · 最终评估 · 2026-06-16*
