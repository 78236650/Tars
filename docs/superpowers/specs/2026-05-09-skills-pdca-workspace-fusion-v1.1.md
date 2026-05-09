# 技能 Agent Skills + PDCA + Workspace 融合设计（v2.5）— v1.1

- **日期**：2026-05-09
- **版本**：v1.1（重写）
- **状态**：✅ 已实施（v2.5 五期全部完成）
- **上游**：v1.0（`skills-pdca-workspace-fusion-v1.0.md`）
- **本版性质**：推翻 v1.0 的私有 SOP 硬脚本方案，完全对齐 Anthropic **Agent Skills** 规范；保留 v2.4 PDCA/Workspace 作为**可选挂件**

## 相对 v1.0 的核心变更

| 维度 | v1.0（推翻） | v1.1（采用） |
|---|---|---|
| 主文件 | `skill.yaml`（私有） | `SKILL.md`（Agent Skills 规范） |
| 前置字段 | 20+ 字段 | 只需 `name` + `description` |
| 触发 | 关键词 + SkillRouter 打分 | **LLM 读 description 自判**（渐进披露） |
| 执行主体 | 硬脚本 `pdca.do[]` YAML | **SKILL.md 自然语言指令**，LLM 按指令执行 |
| 确定性诉求 | YAML 写死，无弹性 | **可选**：技能挂 `scripts/*.py` 或 `pdca.yaml`，LLM 自行决定调用 |
| 迁移现有技能 | 强制 code_assistant/planner → SOP | 不动现有，新体系与旧并存，逐步迁移 |
| 社区兼容 | 不兼容 `anthropics/skills` 生态 | **可直接导入**社区技能 |

## 一、背景与问题

### 1.1 v1.0 方案的三处根本矛盾

1. **和 Agent Skills 行业规范完全偏离**：把技能建模成"YAML 硬脚本"，未来无法复用 `anthropics/skills` 生态
2. **把 code_assistant / planner 强制 SOP 化**：这两个本质是"增强 LLM 思维"的 prompt 模板，不是"固定 pipeline"，改成 SOP 是职责错位
3. **`allow_dynamic_steps` 黑洞**：没定义 AI 在哪个阶段能改什么，不是"死脚本"就是"退化成 task_planner"

### 1.2 v1.1 的核心转向

**技能的本质 = 给 LLM 的"专项说明书"**，不是"执行脚本"。
- 主体是 `SKILL.md`：自然语言写清"这个技能干什么、什么时候用、怎么用"
- LLM 读 description 决定激活、读 SKILL.md 决定如何执行
- **需要确定性**时（如 `deploy`）—— 技能目录下挂 `scripts/` 和 `pdca.yaml`，LLM 在 SKILL.md 指导下调用 → 复用 v2.4 TaskExecutor
- **不需要确定性**时（如 `code_assistant`）—— 只有 SKILL.md，LLM 按指令自由发挥

这让"PDCA 确定性"从"全局强加"变成"技能可选装备"，消除 v1.0 的核心矛盾。

## 二、总体架构

```
用户消息
  │
  ▼
[渐进披露触发]
  Claude 主 LLM 扫描所有技能的 description（前置元数据）
  基于自然语言理解选择 0-N 个技能激活
  不走关键词匹配、不走 SkillRouter 打分
  │
  ▼
[SKILL.md 加载]
  激活的技能 → 读取 SKILL.md 正文注入 system prompt
  如指令中提到 "scripts/xxx.py"、"pdca.yaml"、"references/xxx" → LLM 按需加载
  │
  ▼
[执行]
  ├─ 纯 prompt 型：LLM 按 SKILL.md 指令生成回复（现 code_assistant 类）
  ├─ 脚本型：LLM 调 Bash 运行 scripts/xxx.py（如 webapp-testing）
  └─ PDCA 型：LLM 调 task_planner(pdca_ref="skill://deploy/pdca.yaml")
              → TaskExecutor 读 pdca.yaml 固定步骤 → Workspace 上下文注入
              → StepVerifier 校验 → ActPolicy 决策
  │
  ▼
[完成]
  TaskPanel 展示（若走 PDCA）或普通对话回复
```

## 三、技能目录结构（对齐 Agent Skills）

```
skills/
└── deploy/                      ← 技能目录名 = 技能 id
    ├── SKILL.md                 ← 必需，主文件
    ├── pdca.yaml                ← 可选，PDCA 固定步骤定义
    ├── scripts/                 ← 可选，Python/Shell 辅助脚本
    │   ├── pre_check.py
    │   └── health_check.py
    ├── references/              ← 可选，LLM 按需读取的参考资料
    │   └── deploy_checklist.md
    └── assets/                  ← 可选，静态资源
        └── template.env
```

**关键差异于 v1.0**：
- 不再有 `skill.yaml`（被 `SKILL.md` 取代）
- `pdca.yaml` 变成**可选挂件**，不是每个技能必备
- 加入 `scripts/` `references/` `assets/` 三个标准子目录

## 四、SKILL.md 规范

### 4.1 前置元数据（YAML Frontmatter）

```markdown
---
name: deploy
description: 构建、部署和发布项目。用于用户要求部署、发布、上线、push to production 等操作。自动检测 workspace 下的构建工具（npm/pnpm/pip 等），使用 pdca.yaml 里的确定性步骤执行。
---
```

**字段**：

| 字段 | 必需 | 说明 |
|---|---|---|
| `name` | ✅ | 技能 id，小写短横线，目录名必须一致 |
| `description` | ✅ | **触发的唯一依据**。LLM 读它决定激活。必须同时包含"做什么" + "何时用" |
| `license` | ❌ | 许可证信息 |
| `tars_version_min` | ❌ | TARS 最低版本（TARS 私有扩展，非破坏性） |
| `requires_packages` | ❌ | Python 依赖（TARS 私有） |
| `permissions` | ❌ | `["shell","network","file_write"]` 安装时用户授权（TARS 私有，详见 §7） |

**description 撰写要求**（来自官方 skill-creator 指南）：
- 清晰说明做什么、**何时使用**
- 可以"pushy"一点防止欠触发。例：`"...使用此技能当用户提到部署、发布、上线相关需求，即使未明确要求'部署'一词也应使用"`
- 不要包含关键词列表——LLM 会从 description 自然推断

### 4.2 正文指令（Markdown）

SKILL.md 正文写给 LLM 看，说明"如何完成此技能的任务"。参考 `anthropics/skills/skills/webapp-testing/SKILL.md` 的结构：

```markdown
# Deploy

部署项目到生产环境的确定性工作流。

## Decision Tree

用户请求部署 → workspace 是否 git 仓库？
  ├─ 是 → 读 pdca.yaml 固定步骤（见下）
  └─ 否 → 询问用户是否初始化；拒绝则退化为对话式引导

## 执行流程

**主路径：调用 PDCA 挂件**

调用 task_planner 工具，传入 pdca_ref="skill://deploy/pdca.yaml"，会自动：
- 解析 pdca.yaml 的固定 steps
- 应用 workspace 变量替换（见下）
- 走 TaskExecutor + StepVerifier + ActPolicy

**变量替换**（由 v2.4 Workspace Resolver 提供）：
- `{{workspace.path}}` - 解析到的工作目录
- `{{workspace.pm}}` - 检测到的包管理器（npm/pnpm/yarn/pip）
- `{{workspace.branch}}` - 当前 git 分支

## 辅助脚本

- `scripts/pre_check.py` - 部署前环境检查（磁盘/网络/权限）
- `scripts/health_check.py` - 部署后健康检查

**用法**：`python scripts/pre_check.py --help` 先看参数，再调用。不要读源码（省上下文）。

## 参考文档

- `references/deploy_checklist.md` - 安全部署清单，必要时参考
```

### 4.3 与 v2.4 TaskExecutor 的桥接

`task_planner` tool 增加 `pdca_ref` 参数。LLM 调用示例：

```json
{
  "tool": "task_planner",
  "arguments": {
    "goal": "部署项目",
    "pdca_ref": "skill://deploy/pdca.yaml"
  }
}
```

后端：
1. 解析 `skill://deploy/pdca.yaml` → 定位技能目录
2. 读 `pdca.yaml` → 应用 workspace 变量替换
3. 构造 `TaskPlan` 注入到现有 TaskExecutor
4. 后续走 v2.4 流程（StepVerifier / ActPolicy / artifacts）

## 五、pdca.yaml 规范（可选挂件）

仅**需要确定性执行**的技能才挂 pdca.yaml。纯 prompt 技能无需此文件。

### 5.1 文件格式

```yaml
version: "1.0"
workspace:
  mode: resolve                       # resolve = 走 v2.4 Workspace Resolver 4级优先
  require_git: true                    # 不是 git 仓库则中止
  detect:
    - package_manager                  # 输出 workspace.pm
    - git_branch                       # 输出 workspace.branch
    - tars_version                     # 自动注入

plan:
  hint: "为 {{workspace.path}} 的项目制定构建部署计划，基于下方预定义步骤"

steps:
  - id: 1
    description: "拉取最新代码"
    tool: shell
    arguments: {cmd: "git pull origin {{workspace.branch}}"}
    verify:
      type: exit_code
      expected: 0

  - id: 2
    description: "安装依赖"
    tool: shell
    arguments: {cmd: "{{workspace.pm}} install"}
    verify:
      type: exit_code
      expected: 0

  - id: 3
    description: "执行构建"
    tool: shell
    arguments: {cmd: "{{workspace.pm}} run build"}
    verify:
      type: file_exists
      expected: "dist/index.html"
    expected_artifacts: ["dist/"]

act:
  max_retries: 3
  retry_backoff_s: [1, 2, 4]
  on_final_failure: ask_user           # ask_user | abort | skip
```

### 5.2 变量替换机制

**复用 v2.4 占位符**，扩展点路径（而非另起一套）：

```
{{workspace.path}}          → Workspace Resolver 返回值
{{workspace.pm}}            → 自动检测
{{workspace.branch}}        → git rev-parse --abbrev-ref HEAD
{{step_N.output}}           → v2.4 已有，保持不变
{{step_N.stdout_first_line}} → v2.4 已有，保持不变
{{env.HOME}}                → 环境变量（白名单）
```

**转义**：所有替换值自动 `shlex.quote()` 处理，防命令注入。`{{workspace.pm}} install` 若 pm=`"npm ; rm -rf /"` 被替换为 `'npm ; rm -rf /' install` 不会执行注入。

**检测失败兜底**：`workspace.pm` 检测不到时，pdca.yaml 可声明 `fallback: pip`；未声明 → 该步失败退化为 "询问用户"。

### 5.3 与 SKILL.md 的关系

- SKILL.md 是**给 LLM 的指令**（决定是否/如何调用 PDCA）
- pdca.yaml 是**给 TaskExecutor 的执行定义**（固定步骤）
- LLM 可以选择**不**调用 pdca.yaml，直接按 SKILL.md 指令写自定义 task_planner 步骤
- 这保留 v1.0 想要的"确定性"但不强加

## 六、渐进披露触发机制

### 6.1 核心原则

**不做关键词匹配、不做意图分类**。遵循 Agent Skills 规范：

1. **阶段 1**：LLM 系统提示中列出所有已启用技能的 `name + description`（每个约 100-300 字符，10 个技能约 2-3KB）
2. **阶段 2**：LLM 根据 description 语义理解判断本轮是否需要激活某技能
3. **阶段 3**：激活后读入完整 SKILL.md 正文到 system prompt
4. **阶段 4**：SKILL.md 指令中若引用 `scripts/` 或 `references/`，LLM 按需用 Read 工具读取

### 6.2 相对现有 SkillRouter 的去留

| 组件 | v1.1 决定 |
|---|---|
| SkillRouter 打分（intent*0.5 + entity*0.3 + keyword*0.2） | **淘汰**。LLM 自判取代 |
| `skill.yaml` 的 `trigger.intents / keywords / conditions / priority` | **淘汰**。只保留 `name / description` |
| `lifecycle: per_turn / sticky / session` | **保留**但语义下沉到 SKILL.md 内的自然语言提示（"本技能用完即止" vs "一旦激活持续到会话结束"） |
| `hooks: on_activate / pre_llm / post_llm` | **淘汰**。LLM 在 SKILL.md 中自然编排行为 |
| 手动强制 `/skill <id>` / `/skill off <id>` | **保留**。用户强制激活/禁用的显式控制 |

### 6.3 与 v2.2 Scene Analyzer 的关系

v2.2 的 Scene Analyzer 依然存在，但它的产出（`intent` / `focus_entities`）只用于**记忆系统**（MemoryRouter），**不再**用于技能触发。

技能触发纯靠 LLM 读 description 自判，延迟低（无额外 LLM 调用），准确率高（语义匹配 vs 关键词匹配）。

## 七、安全模型

Agent Skills 规范本身不定义权限系统——由运行环境实现。TARS 的 `permissions` 字段是私有扩展。

### 7.1 权限声明

SKILL.md 前置元数据中声明：

```yaml
permissions:
  - shell              # 可执行 shell 命令
  - file_write         # 可写用户文件系统
  - network            # 可发起 HTTP 请求
  - git_push           # 可推送到远端
```

### 7.2 安装时授权流程

1. 用户通过 SkillHub 或 `/skill install <path>` 安装技能
2. 解析 SKILL.md 前置的 `permissions`
3. 前端弹权限授权对话框（参考 iOS App 权限）：
   - "`deploy` 技能请求以下权限：shell（执行命令）、git_push（推送代码）"
   - 用户逐项 approve / deny / ask_each_time
4. 被 deny 的权限 → SKILL.md 中引用相关 tool 时 LLM 会收到 "该技能无此权限" 提示
5. `ask_each_time` → 首次使用时再弹二次确认

### 7.3 SkillHub 审核

- **官方来源**（`source: anthropic` / `source: tars-official`）：可信，默认权限宽松
- **社区来源**（`source: skillhub`）：
  - 必须带作者签名
  - 社区评分 / 举报机制
  - 危险权限（`shell` + `network` + `file_write` 三合一）安装时强警告

### 7.4 运行时约束

- 已装技能可随时通过 `/skill permissions <id>` 查看当前授权
- `/skill revoke <id> <permission>` 撤销某项权限
- 技能运行时调用超权限的 tool → 立即中止 + 日志告警

## 八、数据模型

### 8.1 数据表变更

```sql
-- v1.1 技能元数据表（新增，替代现 skill.yaml 数据库映射）
CREATE TABLE skills_v3 (
    id TEXT PRIMARY KEY,                 -- = SKILL.md name
    name TEXT NOT NULL,
    description TEXT NOT NULL,            -- 触发的唯一依据
    source TEXT NOT NULL,                 -- local / skillhub / anthropic
    dir_path TEXT NOT NULL,               -- 技能目录绝对路径
    has_pdca BOOLEAN DEFAULT 0,           -- 是否挂 pdca.yaml
    has_scripts BOOLEAN DEFAULT 0,        -- 是否挂 scripts/
    permissions JSON,                      -- ["shell","network",...]
    granted_permissions JSON,              -- 用户实际授权的
    installed_at TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 1
);

-- v2.4 tasks 表扩展
ALTER TABLE tasks ADD COLUMN skill_id TEXT;      -- 哪个技能触发的（NULL = 普通任务）
ALTER TABLE tasks ADD COLUMN pdca_ref TEXT;      -- skill://deploy/pdca.yaml

CREATE INDEX idx_tasks_skill ON tasks(skill_id);
```

### 8.2 现有 skills 表迁移

- 保留现有 `skills` 表（v2.2 格式）一个 minor 版本，新代码读 `skills_v3`
- 启动时一次性迁移：扫描 `skills/*/SKILL.md`（新）+ `skills/*/skill.yaml`（旧）
  - 只有 `skill.yaml` 的 → 兼容读取，回填 `skills_v3`，标 `legacy=1`
  - 有 `SKILL.md` 的 → 直接注册
- 下一个 minor 版本清理 legacy 代码

## 九、现有技能处理

### 9.1 重新评估迁移策略

v1.0 的迁移表**错误**（详见 v1.0 评审）。v1.1 修正：

| 技能 | v1.0 决定 | v1.1 决定 | 理由 |
|---|---|---|---|
| calculator | 不变 | **改 SKILL.md + 保留 PluginSkill 逻辑** | 纯工具但也应升规范 |
| code_assistant | → SOP | **改 SKILL.md**（纯 prompt，无 pdca.yaml） | 编码无固定 pipeline，不适合 SOP |
| planner | → SOP | **改 SKILL.md**（纯 prompt，无 pdca.yaml） | 输出是文档不是执行，职责错位 |
| summarizer | 不变 | **改 SKILL.md** | 同上 |
| translator | 不变 | **改 SKILL.md** | 同上 |

**所有现有技能都升到 SKILL.md 规范**，但只有未来新建的 `deploy` / `run_tests` / `release_notes` 这类才挂 pdca.yaml。

### 9.2 迁移工具

提供 `scripts/migrate_skill_yaml_to_md.py`：
- 读旧 `skill.yaml`
- `prompt_template` → SKILL.md 正文
- `description + trigger.keywords` → 合并为 SKILL.md description（官方 "pushy" 风格改写）
- 保留原字段到 `SKILL.md` 前置作为 TARS 私有扩展
- 人工复核后删除 `skill.yaml`

## 十、第一批内置 PDCA 技能（新建）

**不强制迁移旧技能**，新建三个示范 PDCA 技能演示规范：

| 技能 | description | pdca 步骤 |
|---|---|---|
| `deploy` | 构建部署项目，用于用户要求部署/发布/上线/push to production 时 | git pull → install → build → deploy |
| `run_tests` | 运行项目测试套件并汇总结果，用于用户要求测试/test/验证时 | detect test framework → run → parse report → summary |
| `release_notes` | 从 git log 生成 release notes 并更新 CHANGELOG，用于用户要求发布说明/changelog/release 时 | git log diff → LLM 摘要 → 更新 CHANGELOG.md → 提交 |

这三个作为"官方 PDCA 技能"，同时是后续社区技能的模板。

## 十一、分期上线

| 期 | 时长 | 范围 |
|---|---|---|
| 一 | 3-4d | SKILL.md 解析器 + `skills_v3` 表 + 迁移工具 + 现有技能迁移为 SKILL.md（纯文档转换，不带 PDCA） |
| 二 | 3-4d | task_planner 的 `pdca_ref` 参数 + pdca.yaml 解析 + workspace 变量替换引擎（复用 v2.4 占位符） |
| 三 | 3-4d | 安全模型（permissions 声明 + 安装时授权 UI + 运行时约束） |
| 四 | 2-3d | 三个内置 PDCA 技能（deploy/run_tests/release_notes）+ e2e 测试 |
| 五 | 2d | SkillHub UI 更新（SKILL.md 预览、permissions 展示） + 文档 |

总计 ≈ 2.5-3 周。与 v2.4 任务自动化并行可行——v2.4 完成后 v2.5 第二期可立即开始。

## 十二、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| LLM 漏触发（读 description 不激活）| 技能形同虚设 | description 必须"pushy"撰写；skill-creator 指南明确此点；提供 `/skills list` 手动激活兜底 |
| 多技能同时被激活产生冲突 | 指令打架 | system prompt 中技能按 priority 排序（保留此字段）；LLM 自行仲裁 |
| SKILL.md 膨胀污染上下文 | token 成本 | 渐进披露——只读激活技能的 SKILL.md；scripts/references 按需；强约束 SKILL.md 主体 < 2KB |
| pdca.yaml 变量注入风险 | 命令注入 | shlex.quote 自动转义；白名单环境变量；禁止 `{{user_input}}` 类占位符直接进 shell |
| 社区技能恶意 | 数据泄露 / 远程执行 | permissions 强制声明 + 安装时授权；危险组合警告；审计日志 |
| 现有 SkillRouter 打分逻辑废弃 | 代码删除风险 | 保留一个 minor 版本作 feature flag；验证稳定后清理 |
| 迁移工具质量 | 旧技能转换后失效 | 迁移前自动备份；保留双读（SKILL.md 优先，fallback 到 skill.yaml）一个版本 |

## 十三、开放问题

- SKILL.md 描述里的 "pushy" 程度怎么把控？过度 pushy 导致过触发，欠 pushy 导致漏触发。需提供 skill-creator 辅助脚本跑 eval
- 技能目录的 scripts/ 沙箱级别：是否复用 v2.1 Python Sandbox？shell 脚本呢？
- 社区 SkillHub 的审核流程是否在本期范围？建议延后到 v2.6

## 十四、版本速查

| 议题 | v1.0（推翻） | v1.1（采用） |
|---|---|---|
| 主文件 | skill.yaml | SKILL.md |
| 触发 | 关键词 + Router 打分 | LLM 读 description 自判 |
| PDCA | YAML 硬脚本强制 | pdca.yaml 可选挂件 |
| 变量替换 | 独立 `{pm}` | 统一 `{{workspace.pm}}`，复用 v2.4 |
| 现有技能 | code_assistant 被误迁 SOP | 全部升 SKILL.md，不强制 PDCA |
| 社区生态 | 不兼容 | 与 anthropics/skills 兼容 |
| 安全模型 | 未定义 | permissions + 安装时授权 + 运行时约束 |
| 分期 | 4 期 | 5 期共 2.5-3 周 |

---

*文档版本: v1.1*
*作者: Kiro*
*基于: Agent Skills 官方规范（anthropics/skills）+ v2.4 PDCA + v1.0 失败经验*
*日期: 2026-05-09*
*状态: 草案，待审阅*
