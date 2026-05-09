---
name: release_notes
description: 从 git log 生成 release notes 并更新 CHANGELOG。使用此技能当用户要求发布说明、changelog、release notes、版本记录时。
permissions:
  - shell
  - file_write
---

# Release Notes

从 git commit log 归类生成 release notes 并写入 CHANGELOG.md。

## 执行流程

本技能**不使用** pdca.yaml 固定步骤——release notes 的核心是 LLM 对 commit 消息的语义归类，这个步骤无法用 YAML 写死。改为由你动态生成 task_planner 步骤。

推荐的步骤编排（调 task_planner 时生成）：

1. **收集 commits**：用 `shell` 工具执行 `git log --pretty=format:"%h %s" --no-merges -30` 读取最近 commits
2. **读取现有 CHANGELOG**（可选）：若存在 `CHANGELOG.md`，用 `file` 工具读取找到 Unreleased 段落位置
3. **归类生成内容**：你在本轮回复里把 step 1 的输出按 `feat / fix / docs / chore / refactor` 分类成 markdown，作为 step 4 的输入
4. **写入 CHANGELOG.md**：用 `file_write` 把归类后的 markdown 写到 CHANGELOG.md 的 Unreleased 段落（保留其他段落不动）
5. **确认变更**（可选）：用 `shell` 执行 `git diff CHANGELOG.md` 让用户确认

## 变量替换

因为不走 pdca.yaml，无法使用 `{{workspace.*}}` 自动替换。需要用户确认当前分支时，显式问或用 `shell` 执行 `git rev-parse --abbrev-ref HEAD`。

## 注意事项

- 不要盲目覆盖 CHANGELOG.md 整个文件；只追加到 Unreleased 段落
- 若当前目录不是 git 仓库，直接告诉用户"需要在 git 项目目录下使用本技能"
- commit 消息质量差（如全是 "update" "fix bug"）时，提示用户先规范 commit
