# 认证模型（v4.1.5+）

> 适用范围：所有 `/api/*` 路由（v4.1.5 起统一）
> 状态：当前生效

## 设计目标

1. **单一认证入口**：消除 5+ 处 `try / except: return ...` 静默放过的路由级鉴权反模式。
2. **`tenant_id` 不再可由客户端伪造**：默认从认证用户推导，普通用户通过 header 传 `X-Tenant-Id` 不再生效。
3. **保留管理员快捷调试通道**：`X-User-Role: admin` 头可继续使用，但**必须**配合 admin 用户的 `X-API-Key` 才会被承认。

## 关键概念

### Principal

每次受保护请求都解析为一个 `tars.api._auth.Principal`：

```python
@dataclass
class Principal:
    user_id: str          # 来自 X-API-Key 反查
    role: str             # 'admin' | 'user' | ...
    role_template_id: str
    tenant_id: str        # admin+header → header；其它 → user_id
    is_admin: bool
    api_key: str
```

TARS 当前模型保持「user.id == tenant_id」语义；当未来引入显式租户表时，`Principal.tenant_id` 是唯一需要改的派生点。

### 三种依赖

| 依赖 | 行为 |
| --- | --- |
| `require_authenticated_user` | 必须有效 API key；解析 Principal |
| `require_admin` | 上一条 + `is_admin == True`，否则 403 |
| `require_module(name)` | 必须有效 API key + 模块开关打开 + 角色模板允许该模块 |

## 头部规则

| Header | 普通用户 | Admin 用户 |
| --- | --- | --- |
| `X-API-Key` | **必填**；未带 → 401 | **必填**；未带 → 401 |
| `X-User-Role: admin` | 拒绝 → 403 "X-User-Role admin requires admin api key" | 承认 |
| `X-Tenant-Id` | 忽略（始终 = `user.id`） | 充当 impersonate；写入 `Principal.tenant_id` |

## 迁移指南（旧路由 → 新依赖）

旧写法（已淘汰）：

```python
@router.get("/some")
async def f(
    x_api_key: Optional[str] = Header(None),
    x_tenant_id: Optional[str] = Header("default"),
):
    try:
        user = user_store.get_user_by_api_key(x_api_key)
        if not user:
            return {"error": "auth"}
    except Exception:
        return {"error": "auth"}   # ← 最致命：任何异常都静默放过
    tenant_id = x_tenant_id or "default"
    ...
```

新写法：

```python
from tars.api._auth import require_module, Principal

@router.get("/some")
async def f(principal: Principal = Depends(require_module("insight"))):
    tenant_id = principal.tenant_id
    ...
```

## 启动期初始化

`backend/tars/main.py` 在创建 `UserStore` 之后调用 `init_auth(user_store)`，向 `_auth` 模块注入 user store。`init_insight_api` 启动时再调用 `init_llm_resolver(db)` 完成 InsightForge 侧的依赖注入。

## 审计

下列敏感操作会写入 `audit_logs`，包括 `tenant_id`、`user_id`、`resource_id`：

- `insight.profile.start` / `insight.llm_settings.update`
- `knowledge.ref.read`
- `platform.providers.usage.read`

参见 `tars.utils.audit_compat.safe_audit`。
