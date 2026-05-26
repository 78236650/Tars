---
name: deploy
description: 构建、部署和发布项目。使用此技能当用户要求部署、发布、上线、push to production 等操作。自动检测 workspace 下的构建工具（npm/pnpm/pip 等），使用 pdca.yaml 里的确定性步骤执行。
permissions:
  - shell
  - file_write
  - git_push
triggers:
  - "部署"
  - "发布"
  - "上线"
  - "deploy"
  - "production"
  - "构建并发布"
skip_when:
  - "解释"
  - "什么是"
priority: 70
verify_mode: strict
verify:
  - command: "echo deploy-verify-ok"
    expect: 'stdout contains "deploy-verify-ok"'
    timeout_sec: 10
---

# Deploy

构建并部署项目到目标环境的确定性工作流。

## 执行流程

调用 task_planner 工具，传入 pdca_ref="skill://deploy/pdca.yaml"。系统会自动：
- 解析 pdca.yaml 中的固定步骤（git pull → install → build）
- 应用 workspace 变量替换（{{workspace.pm}}、{{workspace.branch}} 等）
- 走 PDCA 验证循环（每步自动校验，失败重试×3）

## 注意事项

- 若 pdca.yaml 检测到 workspace 不是 git 仓库且 `require_git: true`，会中止并提示用户
- `{{workspace.pm}}` 未检测到包管理器时，pdca.yaml 的 fallback 规则生效（若声明）
- 部署前确认 CHANGELOG/版本号已更新，可通过 release_notes 技能协作
- 如需自定义部署流程（如额外的健康检查、灰度发布），不要使用本技能的 pdca.yaml，改为让 task_planner 生成自定义 steps
