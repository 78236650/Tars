# Skill 编写指南 — triggers / skip_when / verify

> 适用于 TARS v4.3.2+ SKILL.md frontmatter 扩展。

## 基本结构

```yaml
---
name: my_skill
description: 一句话说明何时使用
permissions: [shell]
triggers:
  - "关键词"
  - "正则.*模式"
  - intent:coding.explain
skip_when:
  - "解释.*代码"
  - intent:general_chat
  - context:no_datasource
priority: 70
verify_mode: strict
verify:
  - command: "pytest tests/smoke/ -q"
    expect: exit_code == 0
    timeout_sec: 60
---
```

正文为注入 Agent 的 Markdown 指令（与 v2.5 规范相同）。

## triggers — 何时推荐此技能

| 形式 | 示例 | 说明 |
|------|------|------|
| 关键词 | `"查询数据"` | 消息中包含即匹配 |
| 正则 | `"看一下.*指标"` | Python 正则，忽略大小写 |
| Intent 标签 | `intent:data.analyze` | 与 `signal_extractor` 输出的 intent 匹配（`.` / `_` 等价） |

`priority`（0–100）在多个 skill 同时匹配时用于排序，默认 50。

## skip_when — 何时排除

语法与 `triggers` 相同，额外支持：

| 形式 | 示例 | 说明 |
|------|------|------|
| 上下文 | `context:no_datasource` | 运行时 context 字典中对应键为真时跳过 |

当 **关键词 trigger 已命中** 时，`intent:general_chat` 类 skip 不会生效（避免误杀明确意图）。

## verify — 完成后验证

在 **计划全部步骤执行成功** 后运行（需通过 `skill://your_skill/...` 的 pdca 关联 skill）。

### verify_mode

| 模式 | 行为 |
|------|------|
| `strict`（默认） | 全部 verify 步骤通过才标 done |
| `lenient` | 通过率 ≥ 80%（可配置）→ `done_with_warnings` |

### expect 语法

| 表达式 | 含义 |
|--------|------|
| `exit_code == 0` | 命令退出码 |
| `stdout contains "OK"` | 标准输出包含 |
| `stdout not contains "ERROR"` | 标准输出不包含 |
| `duration_ms < 5000` | 执行耗时 |
| `status_code == 200` | stdout 为纯数字 HTTP 状态码，或配合 `curl -w` |

### 编写原则

1. **只读命令**：`curl -sf`、`pytest`、`test -f`，避免 mutating 操作
2. **短超时**：`timeout_sec` 默认 30，健康检查建议 5–10s
3. **可离线**：CI/内网环境应能在无外部网络下通过 smoke verify

### 示例：deploy

```yaml
verify_mode: strict
verify:
  - command: "curl -sf http://localhost:8000/health"
    expect: exit_code == 0
    timeout_sec: 10
```

本地 smoke（无服务时）：

```yaml
verify:
  - command: "echo deploy-verify-ok"
    expect: 'stdout contains "deploy-verify-ok"'
    timeout_sec: 5
```

## skill.yaml 兼容

旧版 `trigger.intents` / `trigger.keywords` 仍支持，loader 会自动映射为 `triggers`。

也可显式写：

```yaml
triggers:
  - "部署"
skip_when:
  - intent:general_chat
verify:
  - command: "npm test -- --runInBand"
    expect: exit_code == 0
verify_mode: lenient
```

## 调试路由

```bash
cd backend
SKILL_EVAL=1 pytest -m skill_eval tests/test_skill_router.py -q
pytest tests/test_skill_routing_e2e.py -q
```

在 Agent 日志中查看 system prompt 的 **推荐技能 (Router)** 区块。

## 参考实现

- 路由：`backend/tars/skills/router.py`
- 验证：`backend/tars/orchestration/verification.py`
- 示例 skill：`skills/_global/deploy/SKILL.md`、`skills/_global/bi_analytics/SKILL.md`
