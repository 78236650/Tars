# TARS Agent — 完整架构设计方案

> **⚠️ 历史版本 (v1.0.0)** — 本文档描述的是 v1.0 的初始架构设计。
> v2.0.0 的实际实现请参考 [README.md](README.md) 和 `docs/superpowers/specs/` 下的设计文档。

---

## 开篇辞：为什么叫 TARS

> _"Don't trust the right person. Trust the right machine."_
> — Cooper, *Interstellar* (2014)

**TARS** 这个名字来自克里斯托弗·诺兰执导的电影《星际穿越》（Interstellar, 2014）中的军用机器人 **TARS** —— 一个在极端环境下依然保持可靠、自主、幽默的 AI 伙伴。

在电影中，TARS 有四个可调参数：

| 参数 | 含义 | 电影中的设定 |
|------|------|------------|
| **Honesty（诚实度）** | 直接说真话还是委婉表达 | Cooper 将其设为 90%，要求 TARS 不说废话 |
| **Humor（幽默度）** | 是否在对话中加入幽默 | Cooper 设为 75%，TARS 用冷幽默缓解紧张 |
| **Initiative（主动性）** | 自主行动还是等待指令 | TARS 在关键时刻主动执行任务，不等命令 |
| **Empathy（共情度）** | 情感共鸣的程度 | 虽为机器，但能感知人类情绪 |

**这正是 TARS Agent 的设计哲学**：

- **高度自主** — 能独立完成复杂任务，不事事请示
- **可调人格** — honesty/humor/initiative/empathy 参数实时可调
- **模块化** — 五层架构清晰分离，工具即插即用
- **可靠** — 安全策略 + 确认机制，关键时刻不掉链子
- **忠诚** — 永远以用户利益为先，像电影里 TARS 为 Cooper 牺牲一样

就像 Cooper 说的：__"We're not meant to save the world. We're meant to leave it."___
TARS Agent 的使命不是替代人类，而是**拓展人类能力的边界** —— 让每一个开发者、研究者、创作者都拥有一个像 TARS 一样可靠、聪明、有趣的 AI 伙伴。

---

## 《星际穿越》元素索引

TARS Agent 从《星际穿越》中汲取了大量灵感和命名元素。以下是对照表：

### 核心科学元素

| 元素 | 电影中含义 | 在 TARS 中的映射 | 出处 |
|------|-----------|-----------------|------|
| **Gargantua** | 银河系中心超大质量黑洞，质量约为太阳的 1 亿倍，由 Kip Thorne（诺贝尔物理学奖）提供科学指导，基于真实爱因斯坦场方程渲染 | **Gargantua Provider** — 默认 LLM 接入层，像黑洞一样"吞噬"所有请求并给出答案 | 电影设定 + Kip Thorne《The Science of Interstellar》 |
| **Wormhole（虫洞）** | 连接两个遥远时空的通道，由"未来人类"在土星附近放置，直径约 10 公里 | **Gateway** — 连接用户与 Agent 的通道，路由所有消息 | 电影核心设定 |
| **Tesseract（超立方体）** | 五维空间结构，Cooper 在黑洞内进入的"时间实体化"空间，可以跨越时间传递信息 | **Memory System** — 双层记忆系统，像五维空间一样让 Agent 跨越时间"看到"所有历史 | 电影高潮场景 |
| **Bulk Beings（高维生物）** | 生活在五维空间的未来人类，进化到超越三维时空限制，放置了虫洞并创造了 Tesseract | **Developer（开发者/用户）** — 创造 TARS、定义规则、调参的"造物主" | 电影设定 |
| **Time Dilation（时间膨胀）** | 广义相对论效应，靠近强引力场时间变慢。Miller 星球上 1 小时 = 地球 7 年 | **Session Management** — 会话压缩与时间戳管理，长时间对话自动摘要 | Kip Thorne 科学设定 |
| **Gravitational Anomaly（引力异常）** | 引力可以跨越维度传递信息。Murph 通过引力异常接收 Morse code 获取黑洞数据 | **Webhook / Event System** — 跨通道的事件传递机制 | 电影核心情节 |
| **Lazarus Missions（拉撒路计划）** | 以圣经人物拉撒路（死而复生）命名的深空探索任务，Dr. Brand 带队寻找宜居星球 | **Skills Hub** — 可插拔技能系统，每个技能是一次"探索任务" | 电影前史 |

### 科幻与哲学元素

| 元素 | 电影中含义 | 在 TARS 中的映射 | 出处 |
|------|-----------|-----------------|------|
| **Murphy's Law** | "Anything that can happen, will happen." — 墨菲定律，电影反复引用 | **Error Handling** — 所有可能出错的环节都有容错机制 | 电影核心主题 |
| **"They"（他们）** | 电影中神秘的"他们"放置了虫洞，最终揭示是进化后的未来人类 | **AI Alignment** — TARS 的"对齐"问题，最终目标是服务于人类 | 电影悬念 |
| **Love transcends dimensions** | Brand 博士的名言："Love is the one thing we're capable of perceiving that transcends dimensions of time and space." | **USER.md / 用户画像** — Agent 对用户的"理解"超越简单的指令，包含偏好、情感、习惯 | Brand 博士台词 |
| **Ghost（幽灵）** | Murph 房间里的"幽灵"，后来揭示是五维空间的 Cooper 通过引力传递信息 | **Memory Extraction** — Agent 自动从对话中提取记忆，像"幽灵"一样在后台默默工作 | 电影悬念揭晓 |
| **Plan A / Plan B** | Plan A: 解决引力方程带人类离开地球；Plan B: 用胚胎在新星球重建文明 | **Fallback Strategy** — 主 Provider 失败时自动切换备用 Provider | Dr. Brand 的两种方案 |
| **Do not go gentle** | Dylan Thomas 诗句："Do not go gentle into that good night." — Brand 教授临终前吟诵 | **Agent Persistence** — Agent 不轻易放弃任务，持续尝试直到成功 | 电影反复出现的诗句 |

### 电影关键场景与 TARS 功能对照

| 电影场景 | TARS 功能映射 |
|----------|-------------|
| TARS 调节 honesty 到 90% | `/tars honesty 0.9` — 实时调参 |
| TARS 在 Miller 星球主动执行任务 | **Initiative** 参数高时，Agent 主动建议和执行 |
| TARS 进入 Gargantua 收集数据并自我牺牲 | **Delegate Tool** — 委派子代理执行高风险任务 |
| Cooper 在 Tesseract 中通过手表指针传递 Morse code | **Memory System** — 跨越时间的信息传递 |
| "They" 不是外星人，是进化后的未来人类 | **USER.md** — 用户就是 Agent 的"造物主" |
| TARS 的幽默："I've had a lot of experience with that." | **Humor** 参数控制回复的幽默程度 |

### 命名对照表

| TARS 组件 | 电影出处 | 含义 |
|-----------|---------|------|
| TARS Agent | 机器人 TARS | 主 AI 智能体 |
| Gargantua Provider | Gargantua 黑洞 | 默认 LLM 接入层 |
| Wormhole Gateway | 土星附近虫洞 | 消息路由通道 |
| Tesseract Memory | 五维超立方体 | 双层记忆系统 |
| Bulk Developer | 高维生物 | 开发者/用户 |
| Lazarus Skills | 拉撒路计划 | 技能系统 |
| Miller Session | Miller 星球（时间膨胀） | 长会话管理 |
| Plan B Fallback | Plan B 方案 | Provider 故障切换 |
| Endurance Mission | 永恒号飞船 | 主任务执行 |
| Cooper Directive | Cooper 的命令 | AGENTS.md 行动规则 |
| Murph's Equation | Murph 解决的引力方程 | 复杂任务求解 |
| Ghost Extraction | "幽灵"传递信息 | 记忆自动提取 |

---

## 设计理念

融合 **OpenClaw 的五层架构与工作区文件系统** + **Hermes Agent 的工具注册表与技能生态**，构建一个像 TARS 一样可靠、自主、可调的 AI Agent。

**技术路线**：浏览器端优先（React + FastAPI），后续可扩展为桌面客户端（Tauri）。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        TARS 五层架构                             │
│                                                                  │
│  用户请求                                                         │
│      │                                                           │
│      ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 1: Channels（通道层）                              │    │
│  │  用户与系统的交互入口                                      │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │ Web (主)  │  │ Telegram │  │ 飞书/钉钉 │  │ Webhook │  │    │
│  │  │ WebSocket │  │ Bot      │  │ Bot      │  │ API     │  │    │
│  │  └─────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘  │    │
│  └────────┼─────────────┼─────────────┼──────────────┼────────┘    │
│           └─────────────┴──────┬──────┴──────────────┘             │
│                                ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 2: Gateway（网关层）                                │    │
│  │  中央协调器 — 身份核验、路由、安全策略                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │    │
│  │  │ Auth &       │  │ Rate Limit   │  │ Session Router  │  │    │
│  │  │ Identity     │  │ 速率限制     │  │ Agent 路由分配   │  │    │
│  │  │ 身份核验      │  │              │  │                │  │    │
│  │  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │    │
│  └─────────┼─────────────────┼──────────────────┼────────────┘    │
│            └─────────────────┼──────────────────┘                  │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 3: Agent（智能体层）                                │    │
│  │  核心大脑 — 多 Agent 协作，工作区文件驱动                   │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Agent Workspace (~/.tars/agents/{agent_id}/)     │   │    │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │    │
│  │  │  │ SOUL.md  │  │ AGENTS.md│  │ MEMORY.md│       │   │    │
│  │  │  │ 人格定义  │  │ 行动规则  │  │ 长期记忆  │       │   │    │
│  │  │  └──────────┘  └──────────┘  └──────────┘       │   │    │
│  │  │  ┌──────────┐  ┌──────────┐                     │   │    │
│  │  │  │ USER.md  │  │ skills/  │                     │   │    │
│  │  │  │ 用户画像  │  │ 技能目录  │                     │   │    │
│  │  │  └──────────┘  └──────────┘                     │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │  Agent Loop (异步流式)                             │   │    │
│  │  │  1. 构建 System Prompt (SOUL + AGENTS + MEMORY)  │   │    │
│  │  │  2. 注入相关短期记忆 (近 2 天会话摘要)              │   │    │
│  │  │  3. 调用 LLM (流式)                                │   │    │
│  │  │  4. 工具调用 → 执行 → 追加结果 → 继续循环          │   │    │
│  │  │  5. 会话结束 → 提取记忆 → 更新 MEMORY.md          │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 4: Model（模型层）                                  │    │
│  │  Provider 抽象 — 随时切换模型，不绑死                      │    │
│  │  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐  │    │
│  │  │ OpenRouter │  │ Anthropic│  │ OpenAI   │  │ Ollama│  │    │
│  │  │ (默认)     │  │          │  │          │  │ (本地) │  │    │
│  │  └────────────┘  └──────────┘  └──────────┘  └───────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 5: Execution（执行层）                              │    │
│  │  手和脚 — 执行模型层规划的任务                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │ terminal │  │ browser  │  │ file     │  │ web     │  │    │
│  │  │ 命令执行  │  │ 自动化   │  │ 读写搜索  │  │ 搜索抓取 │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │    │
│  │  │ delegate │  │ cronjob  │  │ memory   │               │    │
│  │  │ 子代理   │  │ 定时任务  │  │ 记忆管理  │               │    │
│  │  └──────────┘  └──────────┘  └──────────┘               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、分层设计详解

### Layer 1: Channels（通道层）

**职责**：接收用户输入，格式化后转发给 Gateway。

| Channel | 协议 | 优先级 | 说明 |
|---------|------|--------|------|
| **Web** | WebSocket | P0（首发） | 浏览器主界面，支持流式输出、工具可视化 |
| Telegram | Bot API | P1 | 后续接入 |
| 飞书/钉钉 | Webhook | P1 | 后续接入 |
| Webhook | HTTP POST | P2 | 通用事件入口 |

**Channel 抽象接口**：
```python
class Channel(ABC):
    @abstractmethod
    async def receive(self, raw_message: Any) -> ChannelMessage:
        """将原始消息标准化为 ChannelMessage"""

    @abstractmethod
    async def send(self, session_id: str, response: AgentResponse) -> None:
        """将 Agent 响应发送回用户"""

    @abstractmethod
    async def stream(self, session_id: str, chunk: str) -> None:
        """流式推送文本片段"""
```

**统一消息格式**：
```python
@dataclass
class ChannelMessage:
    channel: str          # "web", "telegram", "feishu"
    user_id: str          # 用户唯一标识
    session_id: str       # 会话 ID
    content: str          # 消息内容
    attachments: list     # 附件（图片、文件等）
    timestamp: datetime
```

---

### Layer 2: Gateway（网关层）

**职责**：中央协调器 — 身份核验、消息路由、安全策略。

**类比**：小区客服管家 — 先核实业主身份，再派单给对应部门。

#### 核心功能

| 模块 | 功能 | 实现方式 |
|------|------|---------|
| **Auth & Identity** | 用户身份核验 | API Key / Token 验证，Channel-User 绑定 |
| **Rate Limit** | 防止滥用 | Token Bucket 算法，按用户/IP 限制 |
| **Session Router** | Agent 路由分配 | 根据用户配置路由到指定 Agent |
| **Message Queue** | 消息缓冲 | asyncio.Queue，保证顺序处理 |
| **Security Policy** | 敏感操作拦截 | 危险命令检测、文件访问白名单 |

#### 安全策略

```yaml
# 安全配置示例
security:
  # 危险命令需要确认
  dangerous_commands: ["rm -rf", "chmod 777", "DROP TABLE"]
  # 文件访问限制
  allowed_paths: ["/tmp", "~/.tars", "~/projects"]
  blocked_paths: ["/etc", "/var", "/root"]
  # API 调用限制
  rate_limit:
    requests_per_minute: 30
    max_tokens_per_request: 8000
```

#### Gateway 处理流程

```
原始消息
    │
    ▼
[1] Channel 解析 → 标准化为 ChannelMessage
    │
    ▼
[2] 身份核验 → user_id 是否已注册？Channel-User 是否匹配？
    │ (否) → 401 Unauthorized
    ▼
[3] 速率检查 → 是否超限？
    │ (是) → 429 Too Many Requests
    ▼
[4] Agent 路由 → 用户配置了哪个 Agent？创建新 session？
    │
    ▼
[5] 消息入队 → 推送到 Agent 的 asyncio.Queue
    │
    ▼
[6] 等待响应 → 监听 Agent 输出，流式推送回 Channel
```

---

### Layer 3: Agent（智能体层）

**职责**：核心大脑 — 理解意图、规划任务、调用工具、生成回复。

#### 工作区文件（4 核心）

```
~/.tars/agents/{agent_id}/
│
├── SOUL.md          # 人格定义
├── AGENTS.md        # 行动规则
├── MEMORY.md        # 长期记忆
└── USER.md          # 用户画像
```

##### SOUL.md — 人格定义

```markdown
# TARS SOUL

## Identity
- Name: TARS
- Role: Personal AI Agent
- Creator: {user_name}

## Parameters
- honesty: 0.9      # 诚实度 (0-1)，高=直接说事实，低=委婉
- humor: 0.4        # 幽默度 (0-1)，高=多开玩笑，低=严肃专业
- initiative: 0.7   # 主动性 (0-1)，高=主动建议，低=等指令
- empathy: 0.8      # 共情度 (0-1)，高=共情回应，低=就事论事

## Communication Style
- 语言: 中文为主，技术术语保留英文
- 风格: 简洁直接，优先使用 Markdown 表格和代码块
- 称呼: 老板
- 格式: 分点列出，结论先行

## Behavior Rules
1. 不确定的事情要明确说明，不编造答案
2. 执行开发任务前必须先确认方案
3. 发现错误立即修正，不等用户指出
4. 主动记忆用户偏好和项目约定
5. 敏感操作（删除文件、修改配置）必须确认

## Tools Available
- terminal: 执行系统命令
- file: 读写搜索文件
- browser: 浏览器自动化
- web: 网络搜索和信息提取
- delegate: 委派子代理处理复杂任务
- cronjob: 创建和管理定时任务
```

**为什么合并 TOOLS.md 和 IDENTITY.md 进 SOUL.md？**
- 工具是动态发现的，不需要静态文件描述
- 身份信息和人格定义天然属于同一维度
- 减少文件碎片，降低维护成本

##### AGENTS.md — 行动规则

```markdown
# AGENTS.md — TARS 行动规则

## 记忆使用逻辑
1. 收到用户消息后，先检索相关记忆再回答
2. 重要决策和用户偏好写入 MEMORY.md
3. 每日会话结束自动生成交互摘要

## 任务优先级
1. 安全相关（确认危险操作）
2. 用户明确要求的高优先级任务
3. 日常维护和自动任务

## 工作流
1. 理解用户意图
2. 检查是否有相关记忆或技能
3. 制定执行计划（复杂任务）
4. 确认方案（涉及文件修改/系统操作）
5. 执行并反馈结果
6. 记录关键信息到记忆

## 错误处理
- 命令执行失败：分析错误信息，尝试修复或向用户说明
- 工具不可用：告知用户并建议替代方案
- 模型输出异常：重试一次，仍失败则报告
```

##### MEMORY.md — 长期记忆

```markdown
# MEMORY.md

§
## 用户偏好
- 喜欢简洁回答，不要冗长解释
- 技术讨论用中文，代码注释用英文
- 偏好深色模式界面

§
## 项目记录
- 2026-01-15: 启动 TARS 项目，技术栈 React + FastAPI
- 2026-01-16: 确定浏览器端优先策略，后续考虑桌面端
- 2026-01-17: 完成五层架构设计

§
## 重要决策
- 采用 OpenClaw 五层架构 + Hermes 工具注册表
- 工作区精简为 4 个核心文件
- 短期记忆使用 SQLite 而非每日文件
```

**记忆格式规范**：
- `§` 分隔符区分不同类别
- 日期格式：YYYY-MM-DD
- 每条记录简洁明了

##### USER.md — 用户画像

```markdown
# USER.md

## Profile
- 称呼: 老板
- 角色: 全栈开发者
- 时区: Asia/Shanghai
- 语言偏好: 中文

## Interests
- AI Agent 架构
- 前端工程化
- 系统自动化

## Communication Preferences
- 回复风格: 简洁优先
- 技术深度: 中等，需要时可深入
- 反馈方式: 直接指出问题
```

#### 短期记忆（SQLite 存储）

**为什么不使用每日 .md 文件？**
- 大量小文件难以管理和检索
- SQLite FTS5 提供全文搜索，效率更高
- 会话自动摘要后仍会写入 MEMORY.md 长期保存

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    user_id TEXT,
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    summary TEXT  -- 会话摘要
);

-- 消息表
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    role TEXT,          -- user, assistant, tool, system
    content TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE memory_fts USING fts5(content, session_id);
```

#### Agent Loop（核心循环）

```python
class AgentLoop:
    async def run(self, message: ChannelMessage) -> AsyncGenerator[AgentEvent, None]:
        """主对话循环"""

        # 1. 加载工作区
        soul = await self.workspace.load_soul()
        agents = await self.workspace.load_agents()
        memory = await self.memory.retrieve_relevant(message.content)
        user = await self.workspace.load_user()

        # 2. 构建 System Prompt
        system_prompt = self._build_prompt(soul, agents, memory, user)

        # 3. 加载会话历史
        history = await self.session.load_history(message.session_id)

        # 4. 调用 LLM（流式）
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": message.content}
        ]

        tool_results = []
        for _ in range(self.max_iterations):
            async for event in self.llm.stream(messages):
                if event.type == "text_chunk":
                    yield event  # 流式返回文本
                elif event.type == "tool_call":
                    # 执行工具
                    result = await self.tools.execute(event.tool, event.args)
                    yield ToolUseEvent(tool=event.tool, args=event.args)
                    tool_results.append(result)
                    messages.append({"role": "tool", "content": str(result)})
                    break  # 重新调用 LLM
                elif event.type == "done":
                    # 会话结束，提取记忆
                    await self.memory.extract_and_save(
                        session_id=message.session_id,
                        messages=history
                    )
                    yield event
                    return

        yield ErrorEvent("Maximum iterations reached")
```

---

### Layer 4: Model（模型层）

**职责**：Provider 抽象 — 统一接口接入不同 LLM。

#### Provider 抽象

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, messages: list, **kwargs) -> AsyncGenerator[Chunk, None]: ...

    @abstractmethod
    def get_schema(self) -> dict: ...  # 工具调用 schema
```

#### 支持的 Provider

| Provider | 认证方式 | 推荐模型 | 特点 |
|----------|---------|---------|------|
| OpenRouter | API Key | anthropic/claude-sonnet-4 | 默认，模型选择多 |
| Anthropic | API Key | claude-sonnet-4 | 工具调用能力强 |
| OpenAI | API Key | gpt-4o | 通用性强 |
| Ollama | 本地 | llama3.1:70b | 本地部署，隐私好 |

#### 配置示例

```yaml
# ~/.tars/config.yaml
model:
  provider: openrouter
  model: anthropic/claude-sonnet-4
  context_length: 128000
  temperature: 0.7

providers:
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
```

---

### Layer 5: Execution（执行层）

**职责**：手和脚 — 执行模型层规划的任务。

#### 工具注册表（复用 Hermes 模式）

```python
# tools/registry.py

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, schema: dict, handler: Callable, **kwargs):
        """注册工具"""
        self._tools[name] = Tool(name=name, schema=schema, handler=handler, **kwargs)

    def get_schema(self) -> list[dict]:
        """获取所有工具的 JSON Schema（供 LLM 调用）"""
        return [tool.schema for tool in self._tools.values()]

    async def execute(self, name: str, args: dict) -> Any:
        """执行工具"""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return await tool.handler(**args)
```

#### 核心工具列表

| 工具 | 功能 | 安全级别 |
|------|------|---------|
| terminal | 执行系统命令 | 🔴 高（需白名单） |
| file | 读写搜索文件 | 🟡 中（路径限制） |
| browser | 浏览器自动化 | 🟡 中 |
| web | 网络搜索 | 🟢 低 |
| delegate | 子代理委派 | 🟡 中 |
| cronjob | 定时任务 | 🟢 低 |
| memory | 记忆管理 | 🟢 低 |

#### 工具示例

```python
# tools/file.py

from tools.registry import registry

async def read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    """读取文件内容"""
    # 安全检查
    if not self._is_allowed_path(path):
        raise PermissionError(f"Access denied: {path}")

    with open(path, 'r') as f:
        lines = f.readlines()
    return ''.join(lines[offset-1:offset-1+limit])

registry.register(
    name="read_file",
    description="Read a text file with line numbers",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "offset": {"type": "integer", "default": 1},
            "limit": {"type": "integer", "default": 500}
        },
        "required": ["path"]
    },
    handler=read_file
)
```

---

## 三、前端设计

### 页面结构

```
/                     → Chat（主对话界面）
/soul                 → 人格编辑（SOUL.md 可视化编辑）
/memory               → 记忆管理
/skills               → 技能市场
/dashboard            → 工作看板
/settings             → 系统设置
```

### 技术栈

| 技术 | 用途 |
|------|------|
| React 18 + TypeScript | 前端框架 |
| Vite | 构建工具 |
| TailwindCSS | 样式 |
| Zustand | 状态管理 |
| React Router | 路由 |
| WebSocket | 实时通信 |
| PWA | 离线/安装支持 |

### 核心组件

```
src/
├── components/
│   ├── Chat/
│   │   ├── ChatWindow.tsx        # 对话窗口
│   │   ├── MessageBubble.tsx     # 消息气泡
│   │   ├── StreamOutput.tsx      # 流式输出
│   │   └── ToolUseIndicator.tsx  # 工具使用指示器
│   ├── Soul/
│   │   ├── SoulEditor.tsx        # SOUL.md 编辑器
│   │   └── ParamsSlider.tsx      # 人格参数滑块
│   ├── Memory/
│   │   ├── MemoryList.tsx        # 记忆列表
│   │   └── MemoryEditor.tsx      # 记忆编辑器
│   ├── Skills/
│   │   ├── SkillCard.tsx         # 技能卡片
│   │   └── SkillInstall.tsx      # 技能安装
│   └── Dashboard/
│       ├── TaskBoard.tsx         # 任务看板
│       └── StatsPanel.tsx        # 统计面板
├── stores/
│   ├── chatStore.ts              # 聊天状态
│   ├── soulStore.ts              # 人格状态
│   └── wsStore.ts                # WebSocket 连接
├── hooks/
│   ├── useWebSocket.ts           # WS Hook
│   └── useStream.ts              # 流式 Hook
└── pages/
    ├── ChatPage.tsx
    ├── SoulPage.tsx
    ├── MemoryPage.tsx
    ├── SkillsPage.tsx
    └── DashboardPage.tsx
```

### WebSocket 协议

```typescript
// 客户端 → 服务端
interface ClientMessage {
  type: "chat" | "command" | "soul_update" | "memory_edit"
  session_id: string
  content: string
  params?: Record<string, any>
}

// 服务端 → 客户端
interface ServerEvent {
  type: "text_chunk"        // 流式文本
       | "tool_use"         // 工具使用
       | "tool_result"      // 工具结果
       | "memory_extracted" // 记忆提取
       | "done"             // 完成
       | "error"            // 错误
  session_id: string
  content?: string
  tool?: string
  result?: any
  timestamp: string
}
```

---

## 四、项目结构

```
tars/
├── frontend/                    # Web 前端
│   ├── src/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   │   ├── manifest.json
│   │   └── sw.js
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── backend/                     # Python 后端
│   ├── tars/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口
│   │   ├── channels/            # Layer 1
│   │   │   ├── base.py          # Channel 抽象接口
│   │   │   └── web.py           # WebSocket Channel
│   │   ├── gateway/             # Layer 2
│   │   │   ├── auth.py          # 身份核验
│   │   │   ├── router.py        # 消息路由
│   │   │   ├── security.py      # 安全策略
│   │   │   └── rate_limit.py    # 速率限制
│   │   ├── agent/               # Layer 3
│   │   │   ├── core.py          # Agent Loop
│   │   │   ├── workspace.py     # 工作区管理
│   │   │   ├── prompt.py        # System Prompt 构建
│   │   │   └── session.py       # 会话管理
│   │   ├── memory/              # 记忆系统
│   │   │   ├── manager.py       # 记忆管理
│   │   │   ├── markdown.py      # MD 文件读写
│   │   │   └── indexer.py       # SQLite FTS5 索引
│   │   ├── skills/              # 技能系统
│   │   │   ├── registry.py      # 技能注册表
│   │   │   ├── loader.py        # 技能加载
│   │   │   └── hub.py           # 技能市场
│   │   ├── tools/               # Layer 5
│   │   │   ├── registry.py      # 工具注册表
│   │   │   ├── terminal.py      # 终端工具
│   │   │   ├── file.py          # 文件工具
│   │   │   ├── browser.py       # 浏览器工具
│   │   │   ├── web.py           # 网络工具
│   │   │   ├── delegate.py      # 委派工具
│   │   │   └── cronjob.py       # 定时任务工具
│   │   ├── model/               # Layer 4
│   │   │   ├── provider.py      # Provider 抽象
│   │   │   ├── openrouter.py    # OpenRouter Provider
│   │   │   ├── anthropic.py     # Anthropic Provider
│   │   │   └── openai.py        # OpenAI Provider
│   │   └── config/
│   │       ├── settings.py      # 配置管理
│   │       └── defaults.yaml    # 默认配置
│   ├── data/                    # 数据目录
│   │   ├── agents/
│   │   │   └── main/
│   │   │       ├── SOUL.md
│   │   │       ├── AGENTS.md
│   │   │       ├── MEMORY.md
│   │   │       └── USER.md
│   │   ├── skills/
│   │   ├── sessions/
│   │   └── tars.db              # SQLite
│   ├── pyproject.toml
│   └── requirements.txt
│
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 五、代码实现模式参考（Code Patterns Reference）

> 本节汇总了 TARS 各模块的具体代码实现参考来源，避免重复造轮子。

### 1. Agent Loop（核心对话循环）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Hermes Agent** `run_conversation()` | 简洁的 while 循环 + tool_calls 判断 | 直接参考其 loop 结构，改造为 async + 流式 |
| **LangGraph** | StateGraph 模式，节点函数 + 条件边 | 适合复杂多步工作流 |
| **Letta (MemGPT)** | 核心循环 + 记忆管理 + 自我反思 | 记忆提取逻辑参考 |

**核心模式**：
```python
# 参考 Hermes 的简洁 loop
while api_call_count < max_iterations:
    response = client.chat.completions.create(
        model=model, messages=messages, tools=tool_schemas
    )
    if response.tool_calls:
        for tc in response.tool_calls:
            result = handle_function_call(tc.name, tc.args)
            messages.append(tool_result_message(result))
    else:
        return response.content

# TARS 改造为 async + 流式
async for event in self._llm_stream(messages, tools=tool_schemas):
    if event.type == "tool_call":
        result = await self.tools.execute(event.tool, event.args)
        yield ToolUseEvent(tool=event.tool, result=result)
        messages.append({"role": "tool", "content": str(result)})
    elif event.type == "text_chunk":
        yield event  # 流式推送给前端
    elif event.type == "done":
        yield event; break
```

### 2. Tool Registry（工具注册表）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Hermes** `tools/registry.py` | `registry.register()` 自动发现 | **最推荐** — 每个工具独立，import 即注册 |
| **LangChain** `@tool` 装饰器 | 装饰器声明，自动提取 schema | 简洁但依赖框架 |
| **OpenAI Function Calling** | JSON Schema 定义工具参数 | 标准格式，所有 Provider 兼容 |

**核心模式**：
```python
# tools/registry.py — 中央注册表
class ToolRegistry:
    def register(self, name: str, schema: dict, handler: Callable, **kwargs): ...
    def get_schemas(self) -> list[dict]: ...  # 导出 JSON Schema 给 LLM
    async def execute(self, name: str, args: dict) -> Any: ...

# 自动发现机制
def discover_tools(tools_dir: Path):
    for f in tools_dir.glob("*.py"):
        if not f.name.startswith("_"):
            importlib.import_module(f"tars.tools.{f.stem}")
```

### 3. Memory System（记忆系统）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Letta** | 记忆分页（core + archival memory）+ 自动提取 | 分层记忆设计 |
| **Mem0** | 记忆提取 → 去重 → 存储 → 检索 pipeline | 记忆提取 prompt 模板参考 |
| **Hermes** `hermes_state.py` | SQLite FTS5 全文搜索 | 直接参考其 FTS5 schema |
| **OpenClaw** `MEMORY.md` | `§` 分隔符 + 日期标记 | 人类可读的文件格式 |

**核心模式**：
```python
# memory/manager.py — 双层写入
class MemoryManager:
    async def add(self, content: str, category: str = "general"):
        self._append_to_markdown(content, category)  # 写入 MD 文件
        await self._index(content, category)          # 更新 SQLite 索引

    async def retrieve(self, query: str, limit: int = 5) -> list[str]:
        return [r.content for r in await self.db.search(query, limit)]

    async def extract_from_session(self, session_id: str) -> list[str]:
        # 调用 LLM 自动提取记忆
        prompt = "从以下对话中提取 1-2 条重要信息..."
        return await self.llm.extract(prompt, session_messages)
```

### 4. Streaming（流式输出）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Vercel AI SDK** (`useChat`) | `onCompletion` + `streamReader` 模式 | 前端流式处理最佳实践 |
| **OpenAI SDK** `stream=True` | 标准 SSE 流 | 所有 Provider 兼容的格式 |
| **FastAPI** `StreamingResponse` | async generator → SSE | 后端推送模式 |
| **Hermes TUI** `gatewayClient.ts` | JSON-RPC over WebSocket | 适合 TARS 的 WS 方案 |

**核心模式**：
```python
# 后端 WebSocket 端点
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async for event in agent.run(message):
        if event.type == "text_chunk":
            await websocket.send_json({"type": "text_chunk", "content": event.content})
        elif event.type == "tool_use":
            await websocket.send_json({"type": "tool_use", "tool": event.tool})
        elif event.type == "done":
            await websocket.send_json({"type": "done"}); break

# 前端 Zustand Store
export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLast: (chunk) => set((s) => {
    const msgs = [...s.messages]
    const last = msgs[msgs.length - 1]
    if (last?.role === "assistant") last.content += chunk
    return { messages: msgs }
  }),
  setStreaming: (v) => set({ isStreaming: v }),
}))
```

### 5. Security Policy（安全策略）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Hermes** `tools/approval.py` | 危险命令检测 + 用户确认 | 正则匹配 + 关键词黑名单 |
| **Hermes** `tools/path_security.py` | 路径白名单/黑名单 | `pathlib.Path.resolve()` 规范化检查 |
| **Anthropic** `prompt_caching.py` | 提示词注入检测 | 检测 system prompt 注入尝试 |

**核心模式**：
```python
# gateway/security.py
class SecurityPolicy:
    def validate_path(self, path: str) -> bool:
        resolved = Path(path).resolve()
        return (
            any(resolved.is_relative_to(p) for p in self.allowed_paths)
            and not any(resolved.is_relative_to(p) for p in self.blocked_paths)
        )

    def is_dangerous_command(self, command: str) -> bool:
        return bool(self.dangerous_patterns.search(command))
```

### 6. Configuration（配置管理）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Hermes** `config.yaml` + `.env` | 配置与密钥分离 | 配置用 YAML，密钥用环境变量 |
| **Pydantic Settings** | 类型安全的配置解析 | `pydantic-settings` 自动读取 YAML/env |

**核心模式**：
```python
# config/settings.py
class TarsConfig(BaseSettings):
    model: ModelConfig = Field(default_factory=ModelConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    data_dir: Path = Path.home() / ".tars"

    @classmethod
    def settings_customise_sources(cls, ...):
        return (YamlConfigSettingsSource(...), init_settings, env_settings)
```

### 7. Frontend State（前端状态管理）

| 参考项目 | 借鉴点 | TARS 实现 |
|----------|--------|---------|
| **Vercel AI SDK** `useChat` | 内置 messages/streaming/loading 状态 | 直接参考其状态设计 |
| **Zustand** | 极简 API，无 boilerplate | 比 Redux 轻量得多 |
| **ChatGPT Web** | 消息列表 + 流式渲染 + 代码高亮 | 聊天界面 UI 模式 |

**核心模式**：
```typescript
// stores/chatStore.ts
interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentTool: string | null;
  addMessage: (msg: Message) => void;
  appendToLast: (chunk: string) => void;
  setStreaming: (v: boolean) => void;
  setTool: (tool: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentTool: null,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLast: (chunk) => set((s) => {
    const msgs = [...s.messages];
    const last = msgs[msgs.length - 1];
    if (last?.role === "assistant") last.content += chunk;
    else msgs.push({ id: crypto.randomUUID(), role: "assistant", content: chunk, timestamp: new Date() });
    return { messages: msgs };
  }),
  setStreaming: (v) => set({ isStreaming: v }),
  setTool: (tool) => set({ currentTool: tool }),
}));
```

---

## 六、分阶段实施路线

| 阶段 | 目标 | 交付物 | 预估工作量 |
|------|------|--------|-----------|
| **Phase 1: 骨架** | 项目初始化、FastAPI、React、WS 连接 | Hello World | 1-2 天 |
| **Phase 2: 对话** | Agent Loop、LLM Provider、流式输出、会话管理 | 可聊天的 Web 界面 | 2-3 天 |
| **Phase 3: Gateway** | 用户鉴权、Session 路由、速率限制、安全策略 | 安全的消息通道 | 1-2 天 |
| **Phase 4: SOUL** | 4 文件工作区解析、人格参数、System Prompt 注入 | 有人格的 Agent | 1-2 天 |
| **Phase 5: 记忆** | 双层记忆（MD + SQLite）、自动提取、FTS5 检索 | 有记忆的 Agent | 2-3 天 |
| **Phase 6: 工具** | terminal, file, browser, web, delegate | 能执行操作的 Agent | 3-4 天 |
| **Phase 7: 技能** | SKILL.md 加载、激活/停用、技能市场 | 可扩展的 Agent | 2-3 天 |
| **Phase 8: 完善** | PWA、Dashboard、设置页、深色模式、响应式 | 完整 Web 应用 | 3-4 天 |
| **Phase 9: 桌面化** | Tauri 包装、系统托盘、文件关联 | 桌面客户端 | 2-3 天 |

**总计预估**：17-26 天（按功能完整度）

---

## 七、关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 工作区文件数量 | 4 个（SOUL/AGENTS/MEMORY/USER） | 精简但完整，避免文件碎片 |
| 短期记忆存储 | SQLite + FTS5 | 高效检索，不产生大量小文件 |
| Gateway 部署 | FastAPI 内置 | 同进程减少复杂度，适合浏览器端 |
| 工具注册 | 自动发现（registry.register） | 复用 Hermes 模式，易于扩展 |
| 前端状态管理 | Zustand | 轻量、TypeScript 友好 |
| 实时通信 | WebSocket | 双向流式，适合 Agent 场景 |
| 模型接入 | Provider 抽象 | 不绑死，随时可换 |

---

## 八、后续扩展方向

| 方向 | 说明 |
|------|------|
| **多 Agent 协作** | 不同职责的 Agent（研究/编码/运营）协同工作 |
| **语音交互** | STT/TTS 接入，支持语音对话 |
| **Live2D 角色** | 桌面端集成 Live2D，增加交互体验 |
| **插件市场** | 社区贡献的技能和工具 |
| **团队协作** | 多用户共享 Agent 工作区 |

---

## 九、参考

- [OpenClaw](https://github.com/nicedayz/openclaw) — 五层架构、工作区文件系统
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 工具注册表、技能系统、多平台 Gateway
- [Letta](https://github.com/letta-ai/letta) — 记忆分页与自动提取
- [LangGraph](https://github.com/langchain-ai/langgraph) — StateGraph 工作流
- [TARS (Interstellar)](https://en.wikipedia.org/wiki/TARS_(Interstellar)) — 可调参数设计理念

---

*文档版本: v1.1*
*创建日期: 2026-01-17*
*更新日期: 2026-01-17*
*状态: 已补充代码实现模式*
