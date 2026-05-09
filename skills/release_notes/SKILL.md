---
name: release_notes
description: 从 git log 生成 release notes 并更新 CHANGELOG。使用此技能当用户要求发布说明、changelog、release notes、版本记录时。
permissions:
  - shell
  - file_write
---

# Release Notes

从 git commit log 自动生成 release notes。

## 执行流程

调用 task_planner 工具，传入 pdca_ref="skill://release_notes/pdca.yaml"。系统会自动：
- git log 提取最近提交
- LLM 摘要归类
- 更新 CHANGELOG.md
