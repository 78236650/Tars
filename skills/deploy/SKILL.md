---
name: deploy
description: 构建、部署和发布项目。使用此技能当用户要求部署、发布、上线、push to production 等操作。自动检测 workspace 下的构建工具（npm/pnpm/pip 等），使用 pdca.yaml 里的确定性步骤执行。
permissions:
  - shell
  - file_write
  - git_push
---

# Deploy

构建并部署项目到目标环境的确定性工作流。

## 执行流程

调用 task_planner 工具，传入 pdca_ref="skill://deploy/pdca.yaml"。系统会自动：
- 解析 pdca.yaml 中的固定步骤（git pull → install → build）
- 应用 workspace 变量替换（{{workspace.pm}}、{{workspace.branch}} 等）
- 走 PDCA 验证循环（每步自动校验，失败重试×3）

## 辅助脚本

- `scripts/pre_check.py` — 部署前环境检查
- `scripts/health_check.py` — 部署后健康检查
