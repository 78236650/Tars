# Web Search + Web Fetch 设计文档

**日期：** 2026-05-06
**状态：** Approved

## 1. 目标

让 Agent 在遇到知识盲区时主动在线检索信息：先用 `web_search` 拿搜索结果列表，必要时用 `web_fetch` 抓某条详情的干净正文。结果通过现有 V3 Reflector 异步沉淀到 archival memory（`source=web`）。

## 2. 当前状态

- 现有 `web` 工具（`backend/tars/tools/builtin/web.py`）只能 fetch 指定 URL 的原始 HTML，对 LLM 来说噪声太大
- 没有任何搜索能力
- 记忆系统 V3 的 Reflector 已经会识别"使用了 web 搜索"并将学到的知识标记为 `source=web` 写入 archival memory（已实现，无需改动）

## 3. 设计

### 3.1 工具拆分

废弃 `web` 工具，拆成两个独立工具：

| 工具 | 用途 |
|------|------|
| `web_search(query, limit=5)` | 给关键词，返回搜索结果列表 |
| `web_fetch(url, max_length=5000)` | 给 URL，返回提取后的干净正文 |

LLM 工作流：先搜 → 看摘要够用就直接回答；不够就 fetch 某条详情。

### 3.2 web_search — SearXNG 集成

调用本地 SearXNG 实例（用户用 Docker 运行）。

```python
class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索网络获取最新信息。当遇到时效性问题、知识盲区时使用。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "最多返回结果数，默认 5，最大 10"},
        },
        "required": ["query"],
    }
```

**实现：**
- 配置：环境变量 `SEARXNG_URL`，默认 `http://localhost:8888`
- 请求：`GET {SEARXNG_URL}/search?q={query}&format=json&engines=google,bing,duckduckgo`
- 解析：从 JSON 响应的 `results` 数组取 `title` / `url` / `content` 字段
- limit 范围：clamp 到 `[1, 10]`
- 超时：10 秒

**输出格式：**
```
搜索结果 (共 N 条):

1. {title}
   {url}
   {content[:200]}

2. ...
```

**错误处理：**
- 连接失败 → `success=False, error="无法连接 SearXNG ({SEARXNG_URL})。请确认服务已启动: docker run -d --name searxng -p 8888:8080 searxng/searxng"`
- 0 结果 → `success=True, output="未找到相关结果"`
- HTTP 错误 → 返回 status code

### 3.3 web_fetch — Readability 正文提取

替代旧 `web` 工具。

```python
class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "获取网页正文内容（自动提取主要文本，去除导航/广告/脚本）。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要获取的网页 URL"},
            "max_length": {"type": "integer", "description": "最大返回字符数，默认 5000"},
        },
        "required": ["url"],
    }
```

**实现：**
- httpx GET 请求（User-Agent: `Mozilla/5.0 TARS-Agent/1.0`，timeout 15s，follow_redirects）
- 用 `trafilatura.extract(html, include_comments=False, include_tables=True)` 提取正文
- 如果 trafilatura 返回 None 或正文 < 100 字符 → fallback：返回原始 HTML 前 max_length 字符 + 标注"⚠️ 未能提取正文，返回原始内容"
- URL 自动补 `https://` 前缀

**输出：**
- 成功：`{title}\n\n{extracted_text}`（trafilatura 也提取标题）
- metadata: `{url, status_code, length, extracted: bool}`

### 3.4 SearXNG 部署

不在 TARS 主流程中处理 SearXNG 启停，由用户手动 Docker 部署：

```bash
docker run -d --name searxng -p 8888:8080 \
  -v searxng_data:/etc/searxng \
  searxng/searxng
```

首次启动时 SearXNG 会拒绝匿名 JSON 请求（默认配置）。需要修改 `/etc/searxng/settings.yml`：
```yaml
search:
  formats:
    - html
    - json
```

文档中给出完整的部署 + 配置步骤。

### 3.5 依赖

- `trafilatura>=1.6` — 加入 `backend/requirements.txt`
- 无新 Python 服务，外部依赖仅 SearXNG Docker

### 3.6 工具注册

`backend/tars/main.py`:
- 移除：`from tars.tools.builtin.web import WebTool` + `tool_registry.register(WebTool())`
- 新增：
  ```python
  from tars.tools.builtin.web_search import WebSearchTool
  from tars.tools.builtin.web_fetch import WebFetchTool
  tool_registry.register(WebSearchTool())
  tool_registry.register(WebFetchTool())
  ```

### 3.7 Agent 集成（已就绪，无需改动）

记忆 V3 Agent 中已有 `used_web_flag` 追踪 `tool_name == "web"`。需要扩展为 `tool_name in ("web", "web_search", "web_fetch")`。

`backend/tars/agent/agent.py` 的 `on_tool_call` 回调中：
```python
if tool_name in ("web", "web_search", "web_fetch"):
    used_web_flag["value"] = True
```

## 4. 数据流

```
用户问"FastAPI 最新版本是什么？"
  → LLM 判断需要搜索
  → web_search(query="FastAPI latest version 2026")
  → 返回 5 条结果（标题 + URL + 摘要）
  → LLM 看摘要够用 → 直接回答 "0.115.0"
  → 或 LLM 需要详情 → web_fetch(url="https://fastapi.tiangolo.com/release-notes/")
  → 返回 trafilatura 提取的 release notes 正文
  → LLM 综合回答
  → Reflector 异步将"FastAPI 最新版本 0.115.0"写入 archival (source=web)
  → 下次问 FastAPI 版本相关问题，archival_search 直接命中，不再调用 web
```

## 5. 文件结构

```
新增：
  backend/tars/tools/builtin/web_search.py
  backend/tars/tools/builtin/web_fetch.py
  backend/tests/test_web_tools.py

删除：
  backend/tars/tools/builtin/web.py

修改：
  backend/tars/main.py                — 工具注册变更
  backend/tars/agent/agent.py         — 扩展 web 工具名匹配
  backend/requirements.txt            — 加 trafilatura
  README.md                           — 文档说明（含 SearXNG 部署步骤）
```

## 6. 测试

`backend/tests/test_web_tools.py`：

**WebSearchTool：**
- mock SearXNG JSON 响应 → 验证解析格式
- 0 结果 → success=True 且 output 提示"未找到"
- 连接失败 → success=False 且 error 含部署提示
- limit 超过 10 → clamp 到 10

**WebFetchTool：**
- mock httpx 响应 + 一段标准 HTML → 验证 trafilatura 提取
- 无正文场景（纯 JS 页面）→ fallback 到原始 HTML 前缀
- HTTP 错误 → success=False
- URL 自动补 https

## 7. 范围之外

- ❌ Search 结果缓存（每次都查最新）— Reflector 沉淀已经起到缓存作用
- ❌ 多搜索引擎抽象层（只支持 SearXNG）
- ❌ JS 渲染页面支持（trafilatura 不处理）
- ❌ SearXNG 自动启停管理（用户自行 Docker 运行）
- ❌ 搜索历史记录页面
- ❌ 速率限制（SearXNG 自身有，TARS 不重复实现）

## 8. 成功标准

1. 用户问"今天有什么 AI 大新闻" → Agent 自动调用 web_search → 返回相关新闻列表 → LLM 总结回答
2. Agent 能用 web_fetch 抓取一个文档页面，返回结构化的正文（不是 HTML 噪声）
3. 同一信息第二次询问时，记忆系统已沉淀，不再重复搜索
4. SearXNG 未启动时给出明确的错误提示（包含 Docker 命令）
