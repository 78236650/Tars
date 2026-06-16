# TARS 记忆系统升级规划 v5.0.5/A3+

> 基于 2026-06-16 记忆体系全面评估，对标 Letta/CoALA/Mem0 前沿方案。
> 前置改动：Phase 1-3（写入去重、增量更新、检索排序）已于同日完成。

## 总体目标

让 TARS 从"被动记事的助手"升级为**"理解用户解决问题思路的智能体"**：
- 能记事 → 能总结解决模式
- 被动检索 → 主动关联提醒
- 碎片记忆 → 结构化经验

## Phase A — 解决思路学习器（Solution Pattern Learner）

**痛点**：用户反复解释同类问题的解决思路，TARS 每次都像第一次听到。

**方案**：Reflector 新增 `log_solution` op，从对话中提取"问题→根因→思路→关键认知"的结构化模式。

```
op: log_solution
problem: 问题的一句话描述
root_cause: 根因
approach: 解决思路（1-3步）
key_insight: 最关键的1条认知
```

- 存储：`memories` 表，`category="solution"`, `memory_type="procedural"`
- 重要性：默认 0.8（高于普通 episodic 的 0.5），衰减更慢
- 检索时自动排到最高优先级

## Phase B — 关联发现器（Cross-Memory Reasoner）

**痛点**：检索返回独立记忆，不利用已有的实体关系图。

**方案**：在 `get_context_for_query` 中，检索后通过 entities/relations 图扩展一轮关联记忆。

```
用户问元洪3号泊位 → 检索匹配记忆 → 实体图: 3号泊位 berth_of 元洪码头
→ 再搜元洪码头相关记忆 → 注入上下文
```

## Phase C — 主动记忆 Agent（Proactive Memory Agent）

**痛点**：用户不问就不翻记忆。

**方案**：每轮对话开始，Scene Analyzer 检测意图后自动检索相关历史决策/偏好，注入 system prompt。

```
## 主动记忆提醒
- 上次你提到3号泊位吃水限制 12.5m，当前计划超限
- 你之前偏好用方案A处理类似场景
```

## Phase D — 步骤记忆（Procedural Memory）

**痛点**：不会记住"做某事的 SOP"。

**方案**：新增 `log_procedure` op，存储结构化步骤。当用户提到 trigger 关键词时自动注入。

```
op: log_procedure
name: 部署TARS到内网
steps: [docker build, 配置nginx, 初始化DB]
triggers: [部署, 内网, 上线]
```

---

*创建日期：2026-06-16 · 对应 VERSION.md v5.0.5/A3+*
