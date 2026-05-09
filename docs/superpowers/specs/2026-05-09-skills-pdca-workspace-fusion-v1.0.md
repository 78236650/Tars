# 技能 SOP + PDCA 执行 + TaskWorkspace 融合设计（v2.5）

- 日期：2026-05-09
- 版本：v1.0
- 状态：草案，待审阅
- 基于：v2.4 任务自动化 + v2.3 技能系统

## 一、问题与目标

### 1.1 当前三个系统各自独立

| 系统 | 能力 | 局限 |
|------|------|------|
| Skills | PromptSkill + PluginSkill | 被动注入，无执行流程控制 |
| PDCA | TaskDetector + TaskExecutor | 只对 task_planner 触发，不与技能联动 |
| Workspace | 4级路径解析 + git | 仅任务自动化解耦使用 |

### 1.2 融合目标

技能升级为带 PDCA 执行控制的 SOP：
```
技能 = 触发条件 + PDCA 工作流 + Workspace 上下文
```

## 二、融合架构

```
用户消息
  → SkillRouter（匹配 type=sop 技能）
    → SOPLoader（加载 skill.yaml）
      → WorkspaceResolver（解析路径 + 检测上下文 + 变量替换）
        → SOPExecutor（Plan→Do→Check→Act 循环）
          → TaskPanel（前端抽屉展示）
```

## 三、核心：type=sop 技能定义

```yaml
id: deploy
type: sop              # 新类型
trigger:
  keywords: ["部署","发布","deploy"]
workspace:
  mode: project_root
pdca:
  plan:
    prompt_template: "为{workspace_path}制定构建部署计划"
  do:
    steps:
      - {tool: shell, cmd: "git pull", verify: {type: exit_code, expected: 0}}
      - {tool: shell, cmd: "{pm} install", verify: {type: exit_code, expected: 0}}
      - {tool: shell, cmd: "{pm} run build", verify: {type: file_exists, expected: "dist/index.html"}}
    allow_dynamic_steps: true
  check:
    global_checks:
      - {verify_type: file_exists, expected: "dist/index.html"}
  act:
    max_retries: 3
    retry_backoff: [1,2,4]
```

### 运行时变量替换

| 变量 | 来源 | 示例 |
|------|------|------|
| {pm} | 项目文件检测 | npm/pnpm/yarn/pip |
| {branch} | git branch | main |
| {workspace_path} | v2.4 resolver | /Users/x/proj |

## 四、复用现有组件

| 现有组件 | 融合后 |
|---------|-------|
| TaskExecutor | Do→Check→Act 引擎（不变） |
| StepVerifier | 校验 pdca.do[].verify |
| ActPolicy | pdca.act 驱动重试/跳过/中止 |
| ArtifactsCollector | 采集产出文件 |
| TaskPanel | 展示 SOP 进度 + skill 标识 |
| SkillRouter | 匹配 type=sop 后触发 SOPExecutor |

## 五、现有技能迁移

| 技能 | 当前 | 迁移 | 理由 |
|------|------|------|------|
| calculator | plugin | 不变 | 纯工具 |
| code_assistant | prompt | → SOP | 编码=读→写→检查→修复 |
| planner | prompt | → SOP | 本身就是 Plan |
| summarizer | prompt | 不变 | 单步生成 |
| translator | prompt | 不变 | 单步翻译 |

## 六、数据模型

```sql
ALTER TABLE tasks ADD COLUMN skill_id TEXT;
ALTER TABLE tasks ADD COLUMN skill_name TEXT;
```

skill_id=NULL 表示普通任务（非 SOP 触发）。

## 七、分期

| 期 | 时长 | 范围 |
|----|------|------|
| 一 | 2-3d | skill.yaml 增强 + SOPSkill 模型 + 变量引擎 |
| 二 | 3-4d | SOPExecutor + tasks.skill_id + SkillRouter 联动 |
| 三 | 2-3d | code_assistant 迁移 + e2e |
| 四 | 2d | SkillHub SOP 分类 + 文档 |

## 八、风险

| 风险 | 缓解 |
|------|------|
| SOP 过度约束 | allow_dynamic_steps 保留 AI 空间 |
| 复杂度上升 | SOP 可选，现有类型不变 |

---

文档版本: v1.0 | 状态: 草案，待审阅 | 日期: 2026-05-09