# TARS 售前管理模块 — 规划方案（v2.0 审核版）

> 版本：v2.0 | 日期：2026-06-02 | 状态：已审核

---

## 零、审核笔记（v2.0 更新摘要）

本轮审核对 v1.0 做了以下修正和补充：

| # | 发现 | 修正 |
|---|------|------|
| 1 | 侧边栏存在**两个组件**：`LeftPanel.vue`（被 `DesktopShell` 实际使用）和 `Sidebar.vue`（备用实现），两处都需加导航项 | 明确两处修改清单 |
| 2 | `LeftPanel.vue` 的 `iconMap` 需要注册 `briefcase` → `lucide:briefcase` 映射 | 在计划中显式标注 |
| 3 | `roles.py` 中 `assign_user_role` 有角色名到 `UserRole` 枚举的映射表，`presales_manager` 需加入 | 明确映射为 `UserRole.USER` |
| 4 | `requirement_analyst` 技能中的 `prompt_template` 缺少 `trigger` 字段的关键词完整性 | 补充更完整的触发词 |
| 5 | 前端设计风格未与现有系统对齐 | 新增第 3.8 节「前端设计一致性规范」 |
| 6 | 技能 `SKILL.md` 需要与 `skill.yaml` **同时存在**（当前系统需要两者） | 为新增技能同时规划双文件 |
| 7 | `LeftPanel` 使用 `icon`（短名）映射到 `lucide:*`，`Sidebar` 直接用 `lucide:*` 全名 | 区分两处写法 |
| 8 | 缺少 `presales_manager` 在 `_role_to_template()` 函数中的映射 | 补充映射 |
| 9 | API 路由的 `require_module("presales")` 守卫需在 `presales.py` 中实际使用 | 补充完整代码示例 |

---

## 一、目标与范围

### 1.1 核心目标

为 TARS 新增「售前管理」模块，使**售前经理**角色能够利用 AI Agent 能力高效完成：

| 工作流 | 说明 |
|--------|------|
| **需求调研** | 引导式需求访谈、智能追问、自动整理需求文档 |
| **方案撰写** | 基于需求 + 历史模板，AI 辅助撰写技术方案/投标书 |
| **历史方案资料库** | 沉淀历史项目方案、标书、技术白皮书，支持智能检索与复用 |
| **汇报 PPT** | 一键生成结构化 PPT 大纲与内容 |
| **端到端工作流** | 客户沟通 → 需求整理 → 方案匹配 → PPT 输出 |

### 1.2 权限范围

- **仅售前经理角色**可访问此页面和功能
- 管理员可分配售前经理权限，但管理员自身**不默认拥有**（`presales` 不在 admin 的 `allowed_modules` 中）
- 模块可见性受 **双重控制**：
  1. `modules.yaml` 全局开关 (`presales.enabled`)
  2. 角色模板 `allowed_modules`（只有 `presales_manager` 角色模板包含 `presales`）

### 1.3 前端权限控制链路

```
用户登录 → restoreFromCache() → initAuth() → initSettings()
  → loadModules() 取 enabledModules
  → loadRoleModules() 取 roleAllowedModules
  → 路由 beforeEach 守卫:
      meta.module === 'presales' &&
      (!enabledModules.includes('presales') || !roleAllowedModules.includes('presales'))
      → 重定向到 '/'
  → LeftPanel/Sidebar visibleNavItems 计算:
      moduleRouteMap['presales'] 匹配 → 双重过滤
```

---

## 二、现有 TARS 能力盘点（可复用清单）

### 2.1 权限与安全体系 ✅ 直接复用

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| 角色模板系统 | `backend/tars/gateway/role_template.py` | 新增 `presales_manager` 内置模板 |
| 模块门控 | `backend/tars/modules/registry.py` | `OPTIONAL_MODULES` 添加 `presales` |
| API 权限守卫 | `backend/tars/api/_auth.py` → `require_module()` | 路由中用 `Depends(require_module("presales"))` |
| 前端路由守卫 | `frontend/src/router/index.ts` → `meta.module` | 添加 `module: 'presales'` |
| JWT / API Key 认证 | `backend/tars/api/_auth.py` | 无需改动 |
| 审计日志 | `backend/tars/security/audit.py` | `safe_audit()` 记录关键操作 |

### 2.2 Agent & AI 能力 ✅ 直接复用

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| LLM 对话引擎 | `backend/tars/agent/` | 售前工作区对话（复用现有 AgentV2） |
| Skill 自动路由 | SkillHub + triggers/keywords | 新增售前专用技能，随对话自动激活 |
| Plan 审批门控 | `plan_gate` (modules.yaml) | 方案生成需审批 |
| Verification Gate | `verification` | 方案质量自动校验 |
| 子 Agent 并发 | `agent_open` + sub-agents | 需求调研 → 方案生成并行分解 |
| 工作区隔离 | `backend/tars/tools/tenant_workspace.py` | 每个售前项目独立工作区 |

### 2.3 知识库 & 文档 ✅ 直接复用/增强

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| Wiki 系统 | `backend/tars/wiki/` + `read_wiki/write_wiki` | 历史方案资料库存储引擎 |
| 知识库 RAG | `backend/tars/knowledge/` + `knowledge_search` | PDF/Word/PPT 文档入库 |
| 文档上传解析 | `backend/tars/knowledge/` + `FileParser` | 历史标书/方案自动解析 |
| 知识库前端组件 | `KnowledgeManager.vue` + `WikiViewer.vue` | 资料库 Tab 内直接复用 |

### 2.4 现有技能 ✅ 直接复用/增强

| 技能 | 位置 | 售前用途 |
|------|------|---------|
| `ppt_outline` | `skills/_global/ppt_outline/` | PPT 大纲生成，需增强为完整内容输出 |
| `doc_writer` | `skills/_global/doc_writer/` | 方案文档撰写，需增强为售前专用prompt |
| `summarizer` | `skills/_global/summarizer/` | 需求会议纪要、沟通摘要 |
| `brainstorm_facilitator` | `skills/_global/brainstorm_facilitator/` | 需求引导式头脑风暴 |
| `interview_prep` | `skills/_global/interview_prep/` | 客户访谈准备 |

### 2.5 编排能力 ✅ 直接复用

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| 多 Agent 编排 | `backend/tars/orchestration/` | 售前工作流模板（预设子任务链） |
| 编排记忆 | `OrchestrationMemory` | 记录每次售前流程的中间产物 |

---

## 三、需要新增/升级的内容

### 3.1 新增角色模板：`presales_manager`

**文件：** `backend/tars/gateway/role_template.py`

在 `BUILTIN_TEMPLATES` 列表末尾（`readonly` 之后）新增：

```python
RoleTemplate(
    id="presales_manager",
    name="售前经理",
    description="售前需求调研、方案撰写、历史资料库、汇报PPT",
    is_builtin=True,
    allowed_tools=[
        "weather", "web_search", "web_fetch",
        "file", "file_list", "file_write",
        "knowledge_search", "read_wiki", "write_wiki",
        "memory",
        "insight_get_workflow", "insight_list_sources",
        "insight_start_forge", "insight_profile_datasource",
        "insight_ask_metric", "insight_explain_metric",
    ],
    denied_tools=[
        "shell", "command", "python_exec",
        "bi_query", "bi_generate_chart",
        "process", "network", "cronjob",
    ],
    allowed_modules=["presales", "knowledge", "insight", "orchestration"],
    workspace_restriction=True,
    max_concurrent=3,
),
```

**同时修改** `backend/tars/api/roles.py` 中的 `assign_user_role` 函数，在 `role_map` 中添加：

```python
role_map = {
    "admin": UserRole.ADMIN,
    "readonly": UserRole.GUEST,
    "presales_manager": UserRole.USER,    # 新增
}
```

**同时修改** `_role_to_template()` 函数：

```python
def _role_to_template(role) -> str:
    if role is None:
        return "standard"
    role_val = role.value if hasattr(role, "value") else str(role)
    return {
        "admin": "admin",
        "user": "standard",
        "guest": "readonly",
        "presales_manager": "presales_manager",   # 新增
    }.get(role_val, "standard")
```

**核心权限说明：** 管理员 (`admin`) 的 `allowed_modules` 不包含 `presales`，因此管理员**不会**在侧边栏看到售前入口。只有被分配了 `presales_manager` 角色模板的用户才能访问。

---

### 3.2 新增模块注册：`presales`

#### 3.2.1 `backend/tars/modules/registry.py`

```python
OPTIONAL_MODULES = (
    "bi", "meeting", "admin", "cron", "insight", "orchestration",
    "presales",  # 新增
)
```

#### 3.2.2 `backend/config/modules.yaml`

```yaml
modules:
  optional:
    presales:
      enabled: true
      description: "售前管理 — 需求调研、方案撰写、历史资料库、汇报PPT"
      routes: ["/api/presales"]
```

---

### 3.3 后端 API 新增

#### 3.3.1 创建 `backend/tars/api/presales.py`

```python
"""售前管理 REST API — v5.1."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import Database
from ._auth import Principal, require_authenticated_user, require_module

router = APIRouter(prefix="/api/presales", tags=["presales"])

_db: Optional[Database] = None

def init_presales_api(db: Database) -> None:
    global _db
    _db = db

def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=503, detail="Presales API not initialized")
    return _db

# ── 请求/响应模型 ──

class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    customer_name: str = ""
    industry: str = ""
    tags: list[str] = []

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    customer_name: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    requirement_summary: Optional[str] = None
    proposal_content: Optional[str] = None
    ppt_outline: Optional[str] = None
    tags: Optional[list[str]] = None

# ── 项目 CRUD ──

@router.get("/projects")
def list_projects(
    principal: Principal = Depends(require_module("presales")),
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """列出售前项目（分页+筛选）。"""
    # ... 实现 ...

@router.post("/projects")
def create_project(
    body: CreateProjectRequest,
    principal: Principal = Depends(require_module("presales")),
):
    """创建售前项目。"""
    # ... 实现 ...

@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    principal: Principal = Depends(require_module("presales")),
):
    """获取项目详情。"""
    # ... 实现 ...

@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    principal: Principal = Depends(require_module("presales")),
):
    """更新项目。"""
    # ... 实现 ...

@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    principal: Principal = Depends(require_module("presales")),
):
    """删除项目。"""
    # ... 实现 ...

# ── 材料管理 ──

@router.post("/projects/{project_id}/materials")
def add_material(project_id: str, ...):
    """上传/关联方案材料。"""

@router.get("/projects/{project_id}/materials")
def list_materials(project_id: str, ...):
    """列出项目材料。"""

# ── AI 生成 ──

@router.post("/generate/proposal")
def generate_proposal(...):
    """AI 生成方案文档。"""

@router.post("/generate/ppt")
def generate_ppt(...):
    """AI 生成 PPT 大纲/内容。"""

# ── 工作流 ──

@router.post("/workflows/requirement")
def start_requirement_workflow(...):
    """启动需求调研工作流。"""

@router.get("/workflows/{workflow_id}/status")
def get_workflow_status(workflow_id: str, ...):
    """查询工作流状态。"""
```

#### 3.3.2 `backend/tars/main.py` 中注册路由

在文件顶部添加 import：

```python
from tars.api.presales import router as presales_router, init_presales_api
```

在路由注册区（`app.include_router` 区域）添加：

```python
if module_registry.is_enabled("presales"):
    app.include_router(presales_router)
```

在 init 区域添加：

```python
if module_registry.is_enabled("presales"):
    init_presales_api(db)
```

#### 3.3.3 数据模型设计

```sql
-- 售前项目表
CREATE TABLE IF NOT EXISTS presales_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    customer_name TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    requirement_summary TEXT DEFAULT '',
    proposal_content TEXT DEFAULT '',
    ppt_outline TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_by TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    tenant_id TEXT DEFAULT 'org_default'
);

-- 售前材料关联表
CREATE TABLE IF NOT EXISTS presales_materials (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    material_type TEXT DEFAULT 'reference',
    title TEXT DEFAULT '',
    wiki_page_name TEXT DEFAULT '',
    knowledge_doc_id TEXT DEFAULT '',
    file_path TEXT DEFAULT '',
    uploaded_by TEXT DEFAULT '',
    created_at TEXT
);

-- 售前工作流记录表
CREATE TABLE IF NOT EXISTS presales_workflows (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    workflow_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    orchestration_task_id TEXT DEFAULT '',
    input_data TEXT DEFAULT '',
    output_data TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    tenant_id TEXT DEFAULT 'org_default'
);
```

状态枚举：
- `draft` — 草稿
- `researching` — 需求调研中
- `proposal_writing` — 方案撰写中
- `completed` — 已完成
- `archived` — 已归档

---

### 3.4 前端页面新增

#### 3.4.1 路由注册（`frontend/src/router/index.ts`）

```typescript
{
  path: '/presales',
  name: 'presales',
  component: () => import('@/views/PresalesView.vue'),
  meta: {
    requiresAuth: true,
    module: 'presales',                              // 模块名，与后端一致
    desktopTitleKey: 'desktop.presales.title',
    desktopSubtitleKey: 'desktop.presales.subtitle',
  }
}
```

关键：`meta.module: 'presales'` 会被路由器 `beforeEach` 守卫校验，确保模块启用且角色有权限。

#### 3.4.2 侧边栏导航修改

**⚠️ 重要：TARS 有两个侧边栏组件，都需要修改。**

##### (A) `frontend/src/components/layout/LeftPanel.vue`（主侧边栏，DesktopShell 使用）

`navItems` 中添加：
```typescript
{ name: 'nav.presales', icon: 'briefcase', path: '/presales' },
```

`moduleRouteMap` 中添加：
```typescript
presales: '/presales',
```

`iconMap` 中添加：
```typescript
'briefcase': 'lucide:briefcase',
```

##### (B) `frontend/src/components/layout/Sidebar.vue`（备用侧边栏）

`navItems` 中添加：
```typescript
{ name: 'nav.presales', icon: 'lucide:briefcase', path: '/presales' },
```

`moduleRouteMap` 中添加：
```typescript
presales: '/presales',
```

##### 过滤逻辑确认

两个侧边栏的 `visibleNavItems` 逻辑已覆盖模块过滤：
- 非模块路由（chat/memory/models/tools/settings）始终显示
- 模块路由检查 `enabledModules.includes(mod)` 和 `roleAllowedModules.includes(mod)`
- 管理员 (`authStore.user?.role === 'admin'`) 仅对 `adminOnly` 标记的路由放行
- **结论：添加后无需修改 filtering 逻辑**

#### 3.4.3 主页面 `PresalesView.vue`

采用 Tab 式布局（参考 `KnowledgeView.vue` 和 `OrchestrationView.vue` 的 Tabs 模式）：

```
┌──────────────────────────────────────────────────────┐
│ DesktopShell header (由 desktopTitleKey/subtitleKey 控制) │
├──────────────────────────────────────────────────────┤
│ ┌─ Tab Bar ────────────────────────────────────────┐ │
│ │ [项目列表] [需求调研] [方案撰写] [PPT生成] [资料库] │ │
│ └──────────────────────────────────────────────────┘ │
│ ┌─ Content Area ───────────────────────────────────┐ │
│ │    根据 activeTab 动态切换子组件                   │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

| Tab | 功能 | 子组件 |
|-----|------|--------|
| 项目列表 | 售前项目 CRUD、状态看板 | `PresalesProjectList.vue` |
| 需求调研 | AI 引导式需求访谈 | `RequirementResearch.vue` |
| 方案撰写 | AI 辅助方案编辑器 | `ProposalEditor.vue` |
| PPT 生成 | PPT 大纲编辑 + 预览 | `PPTGenerator.vue` |
| 资料库 | 内嵌 Wiki + 知识库 | 复用 `WikiViewer.vue` + `KnowledgeManager.vue` |

#### 3.4.4 组件树

```
frontend/src/
├── views/
│   └── PresalesView.vue                    # 主容器（Tab 切换）
├── components/
│   └── presales/
│       ├── PresalesProjectList.vue         # 项目列表 + 看板
│       ├── PresalesProjectCard.vue         # 项目卡片
│       ├── RequirementResearch.vue         # 需求调研对话界面
│       ├── RequirementSummary.vue          # 需求整理结果展示
│       ├── ProposalEditor.vue              # 方案编辑器（Markdown）
│       ├── ProposalPreview.vue             # 方案预览
│       ├── PPTGenerator.vue               # PPT 大纲生成器
│       ├── PPTPreview.vue                  # PPT 内容预览
│       ├── MaterialLibrary.vue             # 资料库浏览
│       └── PresalesWorkflowPanel.vue       # 工作流状态面板
└── api/
    └── index.ts                            # 新增 presalesApi
```

---

### 3.5 技能升级

**⚠️ 技能系统要求：每个技能需要同时存在 `skill.yaml` 和 `SKILL.md` 两个文件。**
当前 `summarizer` 已有双文件，`ppt_outline` 和 `doc_writer` 仅有 `skill.yaml`。

#### 3.5.1 增强 `ppt_outline`（升级至 v2.0）

**文件：** `skills/_global/ppt_outline/skill.yaml`（覆盖原文件）

```yaml
id: ppt_outline
name: PPT 生成
description: 根据需求/方案内容，生成结构化 PPT（大纲+每页内容+演讲备注）
type: prompt
version: "2.0.0"
author: TARS
tags:
  - bundled
  - presales
prompt_template: |
  你是 TARS「PPT 生成」专家。根据提供的售前方案/需求文档，生成完整的演示文稿。

  ## 输出结构
  ### 1. 封面页
  - 标题、副标题、日期、汇报人

  ### 2. 目录页
  - 章节概览（3-5 个章节）

  ### 3. 内容页（每页包含）
  - 页面标题
  - 核心要点（3-5 条 bullet points）
  - 关键数据/图表建议
  - 演讲备注（50 字以内）

  ### 4. 总结页
  - 核心价值主张
  - 下一步行动建议
  - Q&A 提示

  ## 风格要求
  - 商务专业风格
  - 每页信息量适度（不超过 5 个要点）
  - 图表建议具体化（如"柱状图对比方案 A/B 成本"）
  - 使用行业术语但保持客户可理解
parameters:
  - name: audience
    type: string
    description: 受众类型（executive/technical/mixed）
    required: false
    default: mixed
  - name: slide_count
    type: number
    description: 目标页数
    required: false
    default: 15
tars_version_min: "5.0.0"
trigger:
  intents: ["writing.draft"]
  keywords:
    - PPT
    - 演示
    - 汇报
    - slides
    - 幻灯片
    - 演讲
    - presentation
    - 售前演示
  conditions: "any"
priority: 40
lifecycle: "per_turn"
usage: "安装后由 SkillRouter 按消息语义自动激活。"
permissions: []
```

**同时创建** `skills/_global/ppt_outline/SKILL.md`（参考 `summarizer/SKILL.md` 格式）。

#### 3.5.2 增强 `doc_writer`（升级至 v2.0）

**文件：** `skills/_global/doc_writer/skill.yaml`（覆盖原文件）

```yaml
id: doc_writer
name: 方案撰写
description: 售前技术方案、投标书、项目建议书撰写
type: prompt
version: "2.0.0"
author: TARS
tags:
  - bundled
  - presales
prompt_template: |
  你是 TARS「方案撰写」专家，专精于售前技术方案和投标书撰写。

  ## 方案结构模板
  ### 1. 项目背景与需求理解
  - 客户业务痛点分析
  - 需求解读与目标对齐

  ### 2. 解决方案概述
  - 总体技术架构
  - 核心功能模块
  - 关键技术选型与优势

  ### 3. 实施方案
  - 项目阶段划分
  - 里程碑与交付物
  - 风险与应对措施

  ### 4. 团队与案例
  - 项目团队配置
  - 相关成功案例

  ### 5. 商务条款
  - 报价说明
  - 服务承诺与 SLA

  ## 撰写原则
  - 突出差异化优势
  - 量化指标（性能、效率提升百分比）
  - 引用行业标准和最佳实践
  - 语言专业但不晦涩
parameters:
  - name: doc_type
    type: string
    description: 文档类型（proposal/bid/whitepaper/technical_spec）
    required: false
    default: proposal
  - name: industry
    type: string
    description: 目标行业
    required: false
    default: general
tars_version_min: "5.0.0"
trigger:
  intents: ["writing.draft"]
  keywords:
    - 方案
    - 标书
    - 投标
    - 建议书
    - 技术方案
    - proposal
    - RFP
    - RFQ
    - 售前方案
    - 项目方案
  conditions: "any"
priority: 40
lifecycle: "per_turn"
usage: "安装后由 SkillRouter 按消息语义自动激活。"
permissions: []
```

**同时创建** `skills/_global/doc_writer/SKILL.md`。

#### 3.5.3 新增技能：`requirement_analyst`

**创建** `skills/_global/requirement_analyst/skill.yaml`：

```yaml
id: requirement_analyst
name: 需求分析师
description: 结构化需求调研引导，智能追问，生成需求规格说明
type: prompt
version: "1.0.0"
author: TARS
tags:
  - bundled
  - presales
prompt_template: |
  你是 TARS「需求分析师」，负责引导售前需求调研。

  ## 调研流程
  ### 阶段 1: 背景了解
  - 客户行业、规模、现状
  - 项目发起原因和期望目标

  ### 阶段 2: 需求深挖
  - 功能需求（按优先级排列）
  - 非功能需求（性能/安全/可用性）
  - 集成需求（现有系统对接）

  ### 阶段 3: 约束确认
  - 预算范围
  - 时间要求
  - 技术约束（平台/语言/部署环境）

  ### 阶段 4: 输出需求文档
  - 结构化需求整理
  - 优先级矩阵（Must/Should/Could/Won't）
  - 未明确项的追问清单

  ## 交互原则
  - 每次最多问 3 个问题，避免信息过载
  - 对模糊回答进行追问澄清
  - 用客户行业术语沟通
  - 及时总结已确认的需求点
parameters:
  - name: industry
    type: string
    description: 客户行业
    required: false
    default: general
  - name: depth
    type: string
    description: 调研深度（quick/detailed/comprehensive）
    required: false
    default: detailed
tars_version_min: "5.0.0"
trigger:
  intents: ["research.learn", "planning.decompose"]
  keywords:
    - 需求调研
    - 需求分析
    - 需求访谈
    - 客户需求
    - requirement
    - 业务需求
    - 售前需求
    - 投标需求
    - 功能需求
    - 需求规格
  conditions: "any"
priority: 45
lifecycle: "per_turn"
usage: "售前需求调研专用技能。"
permissions: []
```

**同时创建** `skills/_global/requirement_analyst/SKILL.md`。

#### 3.5.4 新增技能：`proposal_matcher`

**创建** `skills/_global/proposal_matcher/skill.yaml`：

```yaml
id: proposal_matcher
name: 方案匹配
description: 根据客户需求从历史方案库中匹配最相似的项目方案
type: prompt
version: "1.0.0"
author: TARS
tags:
  - bundled
  - presales
prompt_template: |
  你是 TARS「方案匹配」专家。根据客户需求描述，从历史方案资料库中检索并推荐最相关的方案。

  ## 匹配维度
  1. 行业匹配度
  2. 功能需求覆盖度
  3. 技术栈相似度
  4. 项目规模可比性

  ## 输出格式
  ### 推荐方案（按匹配度排序）
  - 方案名称
  - 匹配度评分（1-10）
  - 可复用模块清单
  - 需要定制的部分
  - 参考价值说明

  ## 注意事项
  - 优先推荐同行业方案
  - 标注方案的时间（新方案优先）
  - 指明可复用的具体模块和文档段落
tars_version_min: "5.0.0"
trigger:
  intents: ["research.learn"]
  keywords:
    - 匹配方案
    - 历史方案
    - 参考案例
    - 类似项目
    - 方案复用
    - 历史项目
    - 过往案例
    - 售前案例
  conditions: "any"
priority: 40
lifecycle: "per_turn"
usage: "售前方案匹配专用技能。"
permissions: []
```

**同时创建** `skills/_global/proposal_matcher/SKILL.md`。

---

### 3.6 预设编排工作流

在 `backend/tars/orchestration/` 中新增 `presales_workflows.py`：

```python
"""售前预设工作流模板 — v5.1."""

PRESALES_REQUIREMENT_WORKFLOW = {
    "name": "需求调研",
    "steps": [
        {"agent": "requirement_analyst", "task": "分析客户背景，生成调研提纲"},
        {"agent": "brainstorm_facilitator", "task": "发散式收集所有潜在需求"},
        {"agent": "requirement_analyst", "task": "整理并结构化需求，输出需求文档"},
        {"agent": "summarizer", "task": "生成需求摘要和优先级矩阵"},
    ],
}

PRESALES_PROPOSAL_WORKFLOW = {
    "name": "方案撰写",
    "steps": [
        {"agent": "proposal_matcher", "task": "从资料库匹配历史方案"},
        {"agent": "doc_writer", "task": "基于需求和匹配结果生成方案初稿"},
        {"agent": "verification", "task": "审核方案完整性和质量"},
        {"agent": "doc_writer", "task": "根据审核意见修订方案"},
    ],
}

PRESALES_FULL_WORKFLOW = {
    "name": "端到端售前",
    "steps": [
        {"agent": "requirement_analyst", "task": "需求调研"},
        {"agent": "proposal_matcher", "task": "历史方案匹配"},
        {"agent": "doc_writer", "task": "方案撰写"},
        {"agent": "ppt_outline", "task": "PPT 生成"},
        {"agent": "verification", "task": "最终审核"},
    ],
}
```

---

### 3.7 国际化（i18n）

在 `frontend/src/i18n/index.ts` 的 `zh` 对象中新增：

```typescript
// 导航
'nav.presales': '售前管理',

// Desktop 标题
'desktop.presales.title': '售前管理工作台',
'desktop.presales.subtitle': '需求调研、方案撰写、历史资料库与汇报PPT，一站式售前工作流。',

// 售前页面 Tab
'presales.tab.projects': '项目列表',
'presales.tab.research': '需求调研',
'presales.tab.proposal': '方案撰写',
'presales.tab.ppt': 'PPT生成',
'presales.tab.materials': '资料库',

// 项目
'presales.project.create': '新建项目',
'presales.project.name': '项目名称',
'presales.project.customer': '客户名称',
'presales.project.industry': '行业',
'presales.project.status': '状态',
'presales.project.status.draft': '草稿',
'presales.project.status.researching': '调研中',
'presales.project.status.proposal_writing': '方案撰写中',
'presales.project.status.completed': '已完成',
'presales.project.status.archived': '已归档',

// 工作流
'presales.workflow.startResearch': '开始需求调研',
'presales.workflow.generateProposal': 'AI生成方案',
'presales.workflow.generatePPT': 'AI生成PPT',
'presales.workflow.fullFlow': '一键全流程',
'presales.workflow.status': '工作流状态',
'presales.workflow.running': '运行中',
'presales.workflow.completed': '已完成',

// 方案
'presales.proposal.edit': '编辑方案',
'presales.proposal.preview': '预览',
'presales.proposal.export': '导出',
'presales.proposal.template': '方案模板',
'presales.proposal.regenerate': '重新生成',

// PPT
'presales.ppt.outline': 'PPT大纲',
'presales.ppt.slides': '幻灯片',
'presales.ppt.exportPPTX': '导出PPTX',
'presales.ppt.style': '风格',

// 需求
'presales.research.start': '开始调研',
'presales.research.summary': '需求摘要',
'presales.research.export': '导出需求文档',
'presales.research.hint': 'AI 将引导您完成结构化需求调研，每次只问 2-3 个问题。',
```

若项目有英文翻译（`en` 对象），同样需要添加对应英文条目。

---

### 3.8 前端设计一致性规范（新增）

本节确保售前页面与现有 TARS 前端**视觉、交互、组件复用**一致。

#### 3.8.1 色彩系统

使用 Tailwind CSS 自定义 token（定义于 `tailwind.config.js`）：

| Token | 用途 |
|-------|------|
| `bg-surface-0` (`#0c0b09`) | 最底层背景 |
| `bg-surface-1` (`#14110f`) | 卡片/面板背景 |
| `bg-surface-2` (`#1a1511`) | 悬浮层/列表项 hover |
| `text-content-primary` (`#f5f5f4`) | 主文字 |
| `text-content-secondary` (`#d6d3d1`) | 次文字 |
| `text-content-muted` (`#a8a29e`) | 弱化文字 |
| `border-border` (`rgba(245,158,11,0.10)`) | 边框（默认） |
| `bg-accent` (`#d97706`) | 主强调色（amber-600） |
| `bg-accent-soft` (`rgba(217,119,6,0.16)`) | 柔和强调 |

#### 3.8.2 通用组件复用

| 组件 | 路径 | 用法 |
|------|------|------|
| `BaseCard` | `@/components/common/BaseCard.vue` | 卡片容器：`rounded-card border border-border bg-surface-1 p-4` |
| `BaseIcon` | `@/components/common/BaseIcon.vue` | Lucide 图标，如 `<BaseIcon icon="lucide:briefcase" :size="16" />` |
| `BaseButton` | `@/components/common/BaseButton.vue` | 按钮组件 |
| `BaseInput` | `@/components/common/BaseInput.vue` | 输入框组件 |
| `EmptyState` | `@/components/common/EmptyState.vue` | 空状态提示 |
| `AppSurfaceDrawer` | `@/components/common/AppSurfaceDrawer.vue` | 抽屉面板 |
| `AppSurfaceDialog` | `@/components/common/AppSurfaceDialog.vue` | 对话框 |
| `ToastHost` | `@/components/common/ToastHost.vue` | 全局 Toast（无需显式引入） |

#### 3.8.3 布局模式

**Tab 切换**（参考 `KnowledgeView.vue`）：
```vue
<div class="flex shrink-0 gap-1 border-b border-border px-4 pt-3">
  <button
    v-for="tab in tabs" :key="tab.key"
    class="rounded-t-lg px-4 py-2 text-sm font-medium transition"
    :class="activeTab === tab.key
      ? 'border border-b-0 border-border bg-surface-1 text-content'
      : 'text-content-muted hover:text-content'"
    @click="activeTab = tab.key"
  >
    {{ tab.label }}
  </button>
</div>
```

**卡片列表**（参考 `OrchestrationTaskView.vue`）：
```vue
<div class="rounded-2xl border border-border bg-surface-2/60">
  <header class="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
    <h2 class="text-base font-semibold text-content">标题</h2>
  </header>
  <div class="min-h-0 flex-1 overflow-y-auto p-4">
    <!-- 内容 -->
  </div>
</div>
```

**状态标签**（参考 `AgentStatusCard.vue` 的 statusClass）：
```typescript
const statusClass = (status: string) => {
  switch (status) {
    case 'completed': return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    case 'draft':     return 'bg-stone-500/15 text-stone-300 border-stone-500/30'
    case 'researching':
    case 'proposal_writing':
                      return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    default:          return 'bg-slate-500/15 text-slate-300 border-slate-500/30'
  }
}
```

#### 3.8.4 售前专属色建议

为区分售前模块与其他模块，建议为其 Tab 激活态使用**专用点缀色**：

| 场景 | 颜色 | Tailwind |
|------|------|----------|
| Tab 激活态 | 青蓝色 `#0891b2`（cyan-600） | `bg-cyan-600/20 text-cyan-300` |
| 状态标签（进行中） | 沿用 amber 系统 | `bg-amber-500/15 text-amber-300` |
| 成功状态 | 沿用 emerald 系统 | `bg-emerald-500/15 text-emerald-300` |
| 品牌图标 | cyan 色系 | `text-cyan-400` |

#### 3.8.5 侧边栏图标

`LeftPanel.vue` 中图标使用短名（如 `'briefcase'`），通过 `iconMap` 映射为 `lucide:*`。`Sidebar.vue` 中直接使用 `lucide:*` 全名。两者都需更新。

售前管理建议图标：**`lucide:briefcase`（公文包）** 或 **`lucide:file-text`（文档）**。推荐 `briefcase`（公文包），贴合商务场景。

---

## 四、实施路线图

### Phase 1: 基础设施（1-2 天）

```
Day 1: 权限 + 模块注册 + 后端 API 骨架
  ├── [back] 新增 presales_manager 角色模板（role_template.py）
  ├── [back] roles.py 中 role_map + _role_to_template 新增映射
  ├── [back] 注册 presales 模块（registry.py + modules.yaml）
  ├── [back] 创建 presales.py API 骨架 + 路由注册（main.py）
  ├── [back] 数据库迁移（presales_projects/materials/workflows 表）
  └── [back] init_presales_api(db) 启动调用

Day 2: 前端路由 + 骨架页面
  ├── [front] 路由注册（index.ts）
  ├── [front] LeftPanel.vue navItems + moduleRouteMap + iconMap
  ├── [front] Sidebar.vue navItems + moduleRouteMap
  ├── [front] PresalesView.vue 骨架（Tab 布局 + 标题栏）
  ├── [front] i18n 新增（zh + en）
  ├── [front] PresalesProjectList.vue（项目 CRUD 基本功能）
  └── [front] API 层新增 presalesApi（index.ts）
```

### Phase 2: 核心功能（3-5 天）

```
Day 3-4: 需求调研功能
  ├── [skill] 创建 requirement_analyst 技能（skill.yaml + SKILL.md）
  ├── [front] RequirementResearch.vue（对话式需求收集）
  ├── [front] RequirementSummary.vue（需求整理结果）
  ├── [back] 需求调研工作流 API
  └── [back] 需求文档自动保存

Day 5-6: 方案撰写功能
  ├── [skill] 增强 doc_writer → v2.0（skill.yaml + SKILL.md）
  ├── [skill] 创建 proposal_matcher 技能（skill.yaml + SKILL.md）
  ├── [front] ProposalEditor.vue（Markdown 编辑器 + AI 辅助）
  ├── [front] ProposalPreview.vue
  ├── [back] 方案生成 API + 模板管理
  └── [back] 审核工作流

Day 7: 历史资料库
  ├── [front] MaterialLibrary.vue（浏览/检索界面）
  ├── [front] 内嵌 WikiViewer + KnowledgeManager Tab
  ├── [back] 方案自动归档到 Wiki
  └── [back] 智能匹配检索增强
```

### Phase 3: PPT + 工作流完善（2-3 天）

```
Day 8-9: PPT 生成
  ├── [skill] 增强 ppt_outline → v2.0（skill.yaml + SKILL.md）
  ├── [front] PPTGenerator.vue + PPTPreview.vue
  ├── [back] PPT 生成 API
  └── [back] 输出结构化 Markdown（PPTX 导出列为二期）

Day 10: 全流程串联 + 测试
  ├── [test] 端到端工作流测试
  ├── [test] 权限验证测试（普通用户 / 售前经理 / 管理员不可见）
  ├── [test] 模块启停测试（modules.yaml 开关）
  ├── [test] 多角色场景测试
  └── [perf] 性能优化
```

---

## 五、技术架构总览

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Vue 3 + Vite)             │
│  ┌─────────────────────────────────────────────────┐ │
│  │            DesktopShell.vue                       │ │
│  │  ┌───────┬──────────────────────────┬─────────┐  │ │
│  │  │ Left  │  PresalesView.vue        │ Right   │  │ │
│  │  │ Panel │  ┌────────────────────┐  │ Panel   │  │ │
│  │  │       │  │ Tab Bar            │  │         │  │ │
│  │  │       │  ├────────────────────┤  │         │  │ │
│  │  │       │  │ 项目列表 │ 需求调研 │  │         │  │ │
│  │  │       │  │ 方案撰写 │ PPT生成 │  │         │  │ │
│  │  │       │  │ 资料库            │  │         │  │ │
│  │  │       │  └────────────────────┘  │         │  │ │
│  │  └───────┴──────────────────────────┴─────────┘  │ │
│  └─────────────────────────────────────────────────┘ │
│          │  HTTP/WebSocket                            │
│          ▼                                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │              Backend (FastAPI)                    │ │
│  │  ┌───────────┐ ┌──────────┐ ┌────────────────┐  │ │
│  │  │ /presales │ │   Auth   │ │  require_module │  │ │
│  │  │   API     │ │  (JWT)   │ │  ("presales")   │  │ │
│  │  └─────┬─────┘ └──────────┘ └────────────────┘  │ │
│  │        │                                         │ │
│  │  ┌─────┴──────────────────────────────────────┐  │ │
│  │  │              Agent Layer                     │  │ │
│  │  │  ┌──────────┐ ┌───────────┐ ┌───────────┐  │  │ │
│  │  │  │ Skill    │ │ Orchestr- │ │ Plan Gate │  │  │ │
│  │  │  │ Router   │ │ ator      │ │ + Verify  │  │  │ │
│  │  │  └──────────┘ └───────────┘ └───────────┘  │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  │        │                                           │ │
│  │  ┌─────┴──────────────────────────────────────┐  │ │
│  │  │          Data Layer                          │  │ │
│  │  │  ┌──────────┐ ┌───────────┐ ┌───────────┐  │  │ │
│  │  │  │ Presales │ │  Wiki     │ │ Knowledge │  │  │ │
│  │  │  │ DB       │ │  Store    │ │ Base/RAG  │  │  │ │
│  │  │  └──────────┘ └───────────┘ └───────────┘  │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

Skills Layer:
  ┌───────────────────────────────┬──────────────────────────┐
  │  新增 (NEW)                    │  增强 (UPGRADE)           │
  ├───────────────────────────────┼──────────────────────────┤
  │  requirement_analyst v1.0     │  ppt_outline → v2.0      │
  │  proposal_matcher v1.0        │  doc_writer → v2.0       │
  └───────────────────────────────┴──────────────────────────┘
```

---

## 六、风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 生成方案质量不稳定 | 方案不可用 | Plan Gate 审批流程 + 人工审核环节 |
| 历史资料库冷启动 | 匹配准确率低 | 预设行业模板 + 种子方案数据 |
| PPT 导出格式兼容性 | 格式错乱 | 先支持 Markdown，PPTX 导出作为二期 |
| 权限粒度不足 | 售前经理看到不应看数据 | 严格 workspace 隔离 + scope 限制 |
| Sidebar.vue 漏改 | 备用侧边栏不一致 | 明确双组件修改清单（第 3.4.2 节） |
| 技能缺少 SKILL.md | 技能加载失败 | 新技能双文件创建（第 3.5 节） |

---

## 七、关键设计决策

1. **资料库 = Wiki + 知识库双通路**：结构化方案文档走 Wiki（可编辑、版本管理），非结构化历史资料（PDF/Word 标书）走知识库 RAG
2. **工作流 = 编排子系统**：不重复造轮子，售前全流程基于现有的 `MultiAgentOrchestrator`，预设工作流模板
3. **技能 = prompt-based + 双文件**：保持与现有技能体系一致，每个技能需 `skill.yaml` + `SKILL.md`
4. **前端 = 独立 Tab 页 + 模块化路由**：与现有页面模式一致，走 `meta.module` 路由注册，不修改核心聊天逻辑
5. **PPT 生成 = 先大纲后内容**：第一阶段 AI 生成结构化大纲 + 内容（Markdown），第二阶段（可选）集成 python-pptx
6. **管理员不默认持有 presales 权限**：管理员 role 的 `allowed_modules` 不包含 `presales`，需单独分配 `presales_manager` 角色模板
7. **侧边栏双组件同步**：`LeftPanel.vue`（主用）和 `Sidebar.vue`（备用）都需要添加导航项

---

## 八、后续扩展方向（二期）

- 竞品分析自动生成
- 客户画像与决策链分析
- 投标报价辅助计算
- 方案版本对比与 diff（基于 Wiki 版本历史）
- 售前项目数据分析看板（赢单率、行业分布）
- PPTX 格式导出（基于 python-pptx 或类似库）
- 与 CRM 系统集成
