# TARS 售前模块 — 技术可行性与稳定性分析

> 日期：2026-06-02 | 基于实时代码审计

---

## 一、TARS 现有能力盘点（实际可用）

### 1.1 子 Agent 系统 ✅ 成熟

TARS 已有完整的子 Agent 体系（`backend/tars/agent/subagents/`）：

| 子 Agent | 类型 | 能力 | 售前匹配度 |
|---------|------|------|----------|
| `ResearchAgent` | 研究 | 信息检索、综合分析、归纳总结 | ⭐⭐⭐⭐⭐ 需求调研 |
| `WritingAgent` | 写作 | 文体写作、润色编辑、内容创作 | ⭐⭐⭐⭐⭐ 方案撰写 |
| `PlanAgent` | 规划 | 任务分解、步骤规划 | ⭐⭐⭐⭐ 调研计划 |
| `CodeAgent` | 代码 | 编程实现 | ❌ 不需要 |
| `DataAgent` | 数据 | 数据分析、图表 | ⭐⭐ 辅助 |

子 Agent 工作方式：
```
SubAgentManager._determine_agent_type(task)
  → 关键词匹配 → 返回最匹配的 Agent 类型
  → agent.execute(task, context) → 调用 LLM 执行
```

### 1.2 多 Agent 编排器 ⚠️ 港口专用

`MultiAgentOrchestrator` 的 `decompose_goal` 只识别港口关键词：
```python
if any(k in g for k in ["靠泊","泊位","berth"]): → BerthAgent
if any(k in g for k in ["卸","装","堆","箱","yard"]): → YardAgent  
if any(k in g for k in ["船","航次","eta","vessel"]): → VesselAgent
```

**结论：不能直接用于售前。** 需要扩展关键词匹配逻辑。

### 1.3 技能系统 ✅ 成熟

已有 prompt-based 技能自动路由（SkillRouter + triggers/keywords）：
- 用户消息匹配技能关键词 → 自动注入对应 system prompt
- 4 个售前技能已创建（requirement_analyst / doc_writer / ppt_outline / proposal_matcher）

### 1.4 Pipeline 系统 ❌ 不存在

`backend/tars/skills/pipeline_engine.py` — 文件不存在。
`pipelines/` 目录存在但为空。

**结论：Pipeline 不是现成能力，需要新建。**

---

## 二、多 Agent vs 单 Agent 对比分析

### 方案 A：单 Agent + 技能路由（最简单）

```
用户对话 → AgentV2 → SkillRouter 自动匹配技能
                         ↓
              requirement_analyst (调研)
              doc_writer (成文)
              ppt_outline (PPT)
```

| 维度 | 评价 |
|------|------|
| 实现复杂度 | ⭐ 极低（已基本完成） |
| 输出稳定性 | ⭐⭐⭐ 取决于 prompt 质量 |
| 上下文管理 | ⭐⭐ 单 Agent 承载全部上下文 |
| 维护成本 | ⭐ 低 |

**风险：** 单 Agent 的 system prompt 包含所有技能指令，可能稀释每个技能的专注度。

### 方案 B：主 Agent + 子 Agent 委派（推荐）

```
用户对话 → 主 Agent（流程编排 + 结果汇总）
                ↓ 委派
           ┌────┼────┐
           ↓    ↓     ↓
        Research Writing Plan
        Agent   Agent  Agent
        (调研)  (成文)  (规划)
```

| 维度 | 评价 |
|------|------|
| 实现复杂度 | ⭐⭐ 中等（扩展现有 SubAgentManager） |
| 输出稳定性 | ⭐⭐⭐⭐ 每个 Agent 专注一件事 |
| 上下文隔离 | ⭐⭐⭐⭐ 各 Agent 独立 prompt |
| 维护成本 | ⭐⭐ 中（需要协调 Agent 间通信） |

**关键发现：TARS 的 ResearchAgent 和 WritingAgent 已有基础框架，但 prompt 是通用版。**

只需要：
1. 扩展 `SubAgentType` 枚举，新增 `PRESALES_RESEARCH` 和 `PRESALES_WRITING`
2. 创建 `PresalesResearchAgent` 和 `PresalesWritingAgent`，继承现有框架但使用售前专用 prompt
3. 扩展 `SubAgentManager._determine_agent_type` 的关键词映射

### 方案 C：完整多 Agent 编排

```
Orchestrator → 并行执行 Research + Writing → 汇总 → 输出
```

| 维度 | 评价 |
|------|------|
| 实现复杂度 | ⭐⭐⭐⭐ 高（需重写 decompose_goal） |
| 稳定性 | ⭐⭐ 编码器逻辑复杂，端口岸逻辑 |
| 收益 | ⭐⭐ 售前流程是串行的，不需要并行 |

**结论：过度设计，不推荐。**

---

## 三、最终推荐方案

### 推荐：方案 A 为主 + 方案 B 为升级路径

#### Phase 1（当前即可交付）：单 Agent + 技能路由

```
用户在 Chat 中输入 "帮我做一个售前方案"
    ↓
SkillRouter 匹配 → 激活 requirement_analyst 技能
    ↓
Agent 按技能 prompt 引导调研（结构化问卷）
    ↓ (每轮对话自动记录)
用户说 "生成需求报告"
    ↓
Agent 输出格式化需求报告
    ↓
用户说 "基于需求写方案"
    ↓
SkillRouter 匹配 → 激活 doc_writer 技能
    ↓
Agent 按技能 prompt + 参考文档格式生成方案
```

**物：**
- 3 个技能 prompt（已完成）
- 侧边栏「售前」入口 → 创建售前会话（需实现）
- 项目持久化（presales_projects 表，已完成）
- 对话上下文保持（依赖 TARS 现有 session 系统）

**交付周期：1 天**

#### Phase 2（可选升级）：主 Agent + 售前专用子 Agent

当单 Agent 方案在实际使用中发现以下问题时升级：
- 输出质量不稳定（调研和成文互相干扰）
- 生成的方案风格不一致
- 需要更精细的流程控制

升级方式：
```python
# 新增 SubAgentType
class SubAgentType(Enum):
    # ... 现有类型 ...
    PRESALES_RESEARCH = "presales_research"
    PRESALES_WRITING = "presales_writing"

# 新增 Agent
class PresalesResearchAgent(SubAgent):
    # 继承 ResearchAgent，使用售前专用 system prompt
    
class PresalesWritingAgent(SubAgent):  
    # 继承 WritingAgent，使用售前专用 system prompt
    # 自动 RAG 检索知识库
```

**交付周期：1 天（在 Phase 1 基础上）**

---

## 四、交互流程设计

### 4.1 触发方式

| 入口 | 效果 |
|------|------|
| 侧边栏「售前」 | 创建新会话 → 自动发送 "/presales start" → AI 引导立项 |
| 聊天输入 `/presales start 项目名` | 同上 |
| 聊天输入 "帮我做售前方案" | 自然语言激活 |
| 历史项目列表 | 恢复之前的售前对话继续 |

### 4.2 典型交互流程

```
[用户] /presales start 港口数字化项目

[AI] 好的！开始「港口数字化项目」的售前工作。
     
     📋 Stage 1: 项目立项
     请告诉我以下信息：
     1. 客户公司名称？
     2. 所属行业？
     3. 项目预算范围？（可选）

[用户] 深圳港集团，港口物流

[AI] ✅ 项目已创建。
     客户：深圳港集团 | 行业：港口物流
     
     📋 Stage 2: 需求调研
     我会分几个方面了解需求。先看业务背景：
     
     Q1: 项目发起的业务驱动力是什么？
         （比如：集团统一管控需求？新建港区？监管要求？）

[用户] 集团需要统一管控各港区的数字孪生建设

[AI] 了解了。集团级管控需求。
     
     Q2: 目前各港区的信息化建设情况如何？
         哪些港区已有系统？数据是否互通？

[用户] 盐田港区有独立系统，其他港区信息化程度不一

[AI] 📝 已记录：
     - 集团统一管控需求
     - 多港区信息化水平参差不齐
     - 数据孤岛问题
     
     Q3: 期望的核心功能是什么？
         （数字孪生可视化？调度管理？数据分析？）

...（持续多轮对话，AI 自动记录和整理）

[用户] 需求收集差不多了，帮我整理调研报告

[AI] ✅ 生成需求调研报告：
     
     ═══════════════════════════════════
     深圳港集团港口数字化项目
     需求调研报告 V0.1
     
     1. 项目背景
     2. 现状分析
       2.1 业务现状
       2.2 痛点问题
     3. 需求清单（Must/Should/Could）
     ...
     ═══════════════════════════════════
     
     需要调整哪些内容？

[用户] 方案按深圳港 ver6.2 的格式生成

[AI] 好的，按标准格式生成方案初稿：
     
     ═══════════════════════════════════
     深圳港集团数字孪生一体化平台建设方案
     
     第一章 项目概述与战略定位
       1.1 项目背景
       1.2 建设目标
       1.3 研究范围
     
     第二章 现状分析与需求调研
       2.1 业务现状
       2.2 痛点问题
       2.3 需求分析
     
     第三章 总体解决方案
       ...（按9章标准结构）
     ═══════════════════════════════════
```

### 4.3 会话持久化

```
每个售前项目 = 一个 Chat Session
    ↓
对话中自动提取信息 → 更新 presales_projects 表
    ↓
需求报告 / 方案 / PPT → 保存到 session metadata
    ↓
用户可随时返回之前的会话继续
    ↓
项目完成 → 一键归档到知识库/Wiki
```

---

## 五、稳定性保障措施

| 层面 | 措施 |
|------|------|
| **Prompt 质量** | 技能 prompt 经深圳港 ver6.2 文档验证，输出格式严格约束 |
| **上下文管理** | 分阶段推进，每阶段产物持久化到 DB，不依赖长上下文 |
| **错误恢复** | Agent 输出不合法时自动重试，3 次失败后友好提示 |
| **模型切换** | 方案生成等重任务可切换到大模型（Qwen 27B），日常对话用小模型（Qwen 8B） |
| **人工介入点** | 需求确认、方案初稿、最终输出三个节点需要用户确认后才继续 |
| **输出验证** | 方案生成后自动检查章节完整性（9章是否齐全） |

---

## 六、实施建议

**立即实施（Phase 1，1天）：**
1. 侧边栏「售前」入口 → 创建售前会话 → 自动发送引导消息
2. 增强 `requirement_analyst` 技能 prompt（按深圳港 ver6.2 的调研章节格式）
3. 增强 `doc_writer` 技能 prompt（按深圳港 ver6.2 的 9 章结构 + 口吻风格）
4. 端到端测试一条完整对话流程

**暂不实施（Phase 2，待 Phase 1 稳定后）：**
- 拆分为多 Agent（调研 Agent + 成文 Agent）
- 自动 RAG 检索历史方案
- 自动归档到 Wiki

**删除的 v2.0 冗余代码（待清理）：**
- `RequirementResearch.vue`
- `ProposalEditor.vue`
- `PPTGenerator.vue`
- `MaterialLibrary.vue`
