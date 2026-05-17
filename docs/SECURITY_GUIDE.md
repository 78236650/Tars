# TARS 安全配置指南

## 概述

TARS v4.0.0 提供四层安全防护：敏感信息脱敏、提示词注入防护、审计日志、记忆权限隔离。所有安全组件位于 `backend/tars/security/` 模块，通过中间件方式集成，不侵入 Agent 核心逻辑。

---

## 1. 敏感信息脱敏

### 检测模式

| 模式 | 示例 | 掩码结果 |
|------|------|---------|
| API Key | `sk-proj-abc...xyz` | `sk-proj-****xyz` |
| Bearer Token | `Bearer eyJh...` | `eyJ****...` |
| 手机号 | `13812345678` | `138****5678` |
| 邮箱 | `user@company.com` | `***@***` |
| 银行卡 | `6222021234567890` | `6222****7890` |
| 私钥块 | `-----BEGIN RSA PRIVATE KEY-----` | `[PRIVATE KEY REDACTED]` |
| 密码字段 | `"password": "secret"` | `"password": "****"` |

### 工作模式

- **partial**（默认）：保留前缀 + 末 4 位，中间用 `****` 替代
- **redact**：全部替换为 `[REDACTED]`

### 拦截点

1. Agent 输出保存前（`agent.py` 第 647 行）
2. 审计日志参数存储时（`audit.py` 自动脱敏）

### 白名单

```python
from tars.security import sanitizer
sanitizer._whitelist_patterns = [re.compile(r'测试环境')]
# 匹配上下文中含"测试环境"的内容不脱敏
```

---

## 2. 提示词注入防护

### 检测类别

| 类别 | 严重级别 | 处理 |
|------|---------|------|
| Delimiter Injection（`<\|im_start\|>` 等） | medium | 记录日志 |
| Role Override（"ignore previous instructions"） | high | 拦截 + 拒绝 |
| Jailbreak（"DAN mode"、"god mode"） | high | 拦截 + 拒绝 |
| Context Boundary（"end of text"、"new session"） | low | 记录日志 |
| Hidden Command | medium | 记录日志 |

### 处理策略

- **high severity**：拒绝执行，返回警告消息，记入审计日志
- **medium/low**：正常处理，记入审计日志供管理员审查
- **教育讨论**：用户讨论 prompt engineering 本身不触发（检测上下文语境）

### 配置

注入防护在 `agent.py` 的 `handle_message` 入口处执行，仅拦截 `severity == "high"` 的请求。如需调整阈值，修改 `agent.py` 中的判断条件。

---

## 3. 审计日志

### 记录范围

- 所有工具调用（成功/失败）
- 权限拒绝事件
- 记忆操作（读/写/删）
- 模型调用（含 token 数）
- 注入拦截事件

### 查询 API

```
GET /api/audit/logs?action=tool_call&user_id=user1&page=1&page_size=50
```

需要 admin 角色（`X-User-Role: admin` header）。

### 数据结构

```json
{
  "id": 1,
  "tenant_id": "user1",
  "user_id": "user1",
  "action": "tool_call:success",
  "resource_type": "tool",
  "resource_id": "web_search",
  "detail": "{\"query\": \"天气\"}",
  "client_ip": "192.168.1.100",
  "created_at": "2026-05-17T10:30:00+08:00"
}
```

---

## 4. 记忆权限

### 作用域

| Scope | 可见性 | 写入权限 |
|-------|--------|---------|
| private（默认） | 仅本用户 | 本用户 + admin |
| shared | 所有用户可读 | 仅 admin |

### 权限矩阵

| 操作 | 同租户 | 跨租户 | admin |
|------|--------|--------|-------|
| 读 private | ✅ | ❌ | ✅ |
| 读 shared | ✅ | ✅ | ✅ |
| 写 private | ✅ | ❌ | ✅ |
| 写 shared | ❌ | ❌ | ✅ |

### 检索行为

记忆检索自动包含 shared 记忆：
```sql
WHERE (tenant_id = ? OR scope = 'shared')
```

### Admin 管理 API

```
GET    /api/admin/memory/users              — 所有用户记忆统计
GET    /api/admin/memory/users/{id}         — 用户记忆详情
DELETE /api/admin/memory/users/{id}/purge   — 清空用户私有记忆
POST   /api/admin/memory/shared            — 创建共享记忆
DELETE /api/admin/memory/shared/{id}        — 删除共享记忆
PUT    /api/memory/{id}/scope              — 修改记忆 scope（admin only）
```

---

## 5. 工具权限

### 配置文件

`backend/config/tool_permissions.yaml`:

```yaml
roles:
  admin:
    allowed_tools: "*"
    workspace_restriction: false
  user:
    allowed_tools:
      - weather
      - web_search
      - web_fetch
      - file
      - file_write
      - python_exec
      - memory
      - command
      - knowledge_search
    denied_tools:
      - shell
      - process
      - network
    workspace_restriction: true
  guest:
    allowed_tools:
      - weather
      - web_search
    workspace_restriction: true
```

### 行为

- 用户调用未授权工具时，返回权限拒绝错误
- 拒绝事件自动记入审计日志
- admin 角色不受限制

---

*文档版本: v4.0.0 | 更新日期: 2026-05-17*
