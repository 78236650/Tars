# SkillHub 商店功能增强计划

## 1. 问题分析

### 当前状态
- 后端 `SkillHubCLI.search()` 依赖本地 `skillhub` CLI 命令
- 但 SkillHub CLI 只有 `search` 和 `install` 命令（用于安装到本地）
- CLI 的 `search` 是从本地已下载索引搜索，不返回可下载的技能列表
- 前端打开 SkillHub 弹窗后看不到任何可下载的技能

### 目标
在 Tools 页面的 SkillHub 商店弹窗中，无需安装 CLI 即可看到：
1. **热门推荐技能**（精选推荐列表）
2. **搜索功能**（关键词搜索）

## 2. 解决方案

### 后端改动

#### 文件 1: `backend/tars/execution/skillhub.py`
**改动内容：**
1. 新增 `SkillHubAPI` 类，封装对 SkillHub 网站的 HTTP 调用
   - `get_featured()` - 获取精选推荐
   - `search(query)` - 搜索技能
   - `get_detail(skill_name)` - 获取技能详情
2. 新增 FastAPI 端点：
   - `GET /api/tools/skillhub/featured` - 获取精选推荐
   - `GET /api/tools/skillhub/detail/{skill_name}` - 获取技能详情
3. 修改现有端点 `POST /api/tools/skillhub/search` 改用 SkillHub 网站 API

**API 设计：**
```python
# GET /api/tools/skillhub/featured
Response: {
    "success": true,
    "skills": [
        {
            "id": "summarize",
            "name": "Summarize",
            "description": "Summarize URLs, files, YouTube videos",
            "author": "steipete",
            "downloads": 411000,
            "favorites": 745,
            "icon": "S",
            "category": "信息处理",
            "install_command": "skillhub install summarize"
        },
        ...
    ]
}

# GET /api/tools/skillhub/detail/summarize
Response: {
    "success": true,
    "skill": {
        "id": "summarize",
        "name": "Summarize",
        "description": "...",
        "content": "# Summarize\n...",
        "author": "steipete",
        "downloads": 411000,
        "version": "1.0.0"
    }
}
```

#### 文件 2: `backend/tars/api/tools.py`
**改动内容：**
1. 新增路由 `@router.get("/skillhub/featured")`
2. 新增路由 `@router.get("/skillhub/detail/{skill_name}")`
3. 修改 `search_skillhub` 使用网站 API

### 前端改动

#### 文件: `frontend/src/views/ToolsView.vue`
**改动内容：**
1. 新增状态：
   - `skillhubFeatured` - 精选推荐列表
   - `skillhubLoading` - 加载状态
2. 新增函数：
   - `loadSkillhubFeatured()` - 加载精选推荐
   - `installSkill(skillName)` - 安装技能（使用安装命令）
3. 修改 SkillHub 弹窗 UI：
   - 打开时自动加载精选推荐
   - 显示热门技能卡片列表
   - 每个卡片有名称、描述、下载量、安装按钮
   - 保留搜索功能

**UI 设计：**
```
┌─────────────────────────────────────────────┐
│  🛒 SkillHub 商店                      [X]  │
├─────────────────────────────────────────────┤
│  [搜索框........................] [搜索]   │
│                                             │
│  精选推荐                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ S Summarize│ │ F Find-Skills│ │ G Github │  │
│  │ 信息处理  │ │ 工具      │ │ 开发工具 │   │
│  │ ⬇️ 41.1万 │ │ ⬇️ 40.2万 │ │ ⬇️ 26.6万 │   │
│  │ [安装]   │ │ [安装]   │ │ [安装]   │   │
│  └──────────┘ └──────────┘ └──────────┘   │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ W Weather │ │ ...      │ │ ...      │   │
│  │ ...      │ │          │ │          │   │
│  └──────────┘ └──────────┘ └──────────┘   │
└─────────────────────────────────────────────┘
```

## 3. 实现步骤

1. [ ] 修改 `backend/tars/execution/skillhub.py` - 新增 `SkillHubAPI` 类
2. [ ] 修改 `backend/tars/api/tools.py` - 新增 featured 和 detail API
3. [ ] 修改 `frontend/src/views/ToolsView.vue` - 新增精选推荐 UI
4. [ ] 重启后端服务测试 API
5. [ ] 刷新前端页面验证功能

## 4. 验证标准

- [ ] 打开 SkillHub 弹窗后立即看到热门技能列表
- [ ] 搜索功能能返回搜索结果
- [ ] 安装按钮能触发安装（调用 API 或打开终端）
- [ ] 页面样式美观，符合现有设计风格
