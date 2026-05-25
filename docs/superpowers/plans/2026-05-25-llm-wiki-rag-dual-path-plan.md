# LLM Wiki + RAG 双路径知识系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 LLM Wiki 编译管线，与现有 RAG 并存，通过统一入口自动路由，agent 通过 read_wiki 工具按需查阅结构化知识。

**Architecture:** 新增 WikiCompiler（事件驱动编译）+ WikiRagRouter（规则+LLM 路由）+ read_wiki 工具 + Wiki CRUD API。Wiki 以 Markdown 文件存储在 `data/wiki/`，index.md 摘要注入 system prompt。

**Tech Stack:** Python/FastAPI, asyncio, LLM (via existing provider), Markdown files, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/tars/wiki/__init__.py` | Package init |
| `backend/tars/wiki/compiler.py` | WikiCompiler: LLM 增量编译素材到 wiki 页面 |
| `backend/tars/wiki/router.py` | WikiRagRouter: 规则+LLM 判断文件走 wiki 还是 rag |
| `backend/tars/wiki/store.py` | WikiStore: 读写 wiki 目录下的 markdown 文件 |
| `backend/tars/api/wiki.py` | Wiki REST API endpoints |
| `backend/tars/tools/builtin/wiki_read.py` | read_wiki 工具 |
| `backend/tests/test_wiki_router.py` | 路由判断测试 |
| `backend/tests/test_wiki_store.py` | Wiki 存储测试 |
| `backend/tests/test_wiki_compiler.py` | 编译流程测试 |
| `backend/tests/test_wiki_api.py` | API 端点测试 |
| `frontend/src/components/knowledge/WikiViewer.vue` | Wiki 浏览页面 |

---

## Task 1: WikiStore — Wiki 文件存储层

**Files:**
- Create: `backend/tars/wiki/__init__.py`
- Create: `backend/tars/wiki/store.py`
- Create: `backend/tests/test_wiki_store.py`

- [ ] **Step 1: Write failing tests for WikiStore**

```python
# backend/tests/test_wiki_store.py
import pytest
from pathlib import Path
from tars.wiki.store import WikiStore


@pytest.fixture
def wiki_store(tmp_path):
    return WikiStore(wiki_dir=tmp_path)


def test_init_creates_index(wiki_store, tmp_path):
    assert (tmp_path / "index.md").exists()


def test_write_page(wiki_store):
    wiki_store.write_page("port-ops", "# 港口运营\n\n泊位分配规则...")
    content = wiki_store.read_page("port-ops")
    assert "港口运营" in content


def test_read_nonexistent_page(wiki_store):
    assert wiki_store.read_page("nonexistent") is None


def test_list_pages(wiki_store):
    wiki_store.write_page("page-a", "# A")
    wiki_store.write_page("page-b", "# B")
    pages = wiki_store.list_pages()
    assert set(pages) == {"page-a", "page-b"}


def test_delete_page(wiki_store):
    wiki_store.write_page("temp", "# Temp")
    wiki_store.delete_page("temp")
    assert wiki_store.read_page("temp") is None


def test_update_index(wiki_store):
    wiki_store.write_page("vessel", "# 船舶调度")
    wiki_store.update_index({"vessel": "船舶调度相关知识"})
    index = wiki_store.read_index()
    assert "vessel" in index
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_store.py -v`
Expected: FAIL — module `tars.wiki.store` not found

- [ ] **Step 3: Implement WikiStore**

```python
# backend/tars/wiki/__init__.py
```

```python
# backend/tars/wiki/store.py
from pathlib import Path
from typing import Optional


class WikiStore:
    def __init__(self, wiki_dir: Path):
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.wiki_dir / "index.md"
        if not index_path.exists():
            index_path.write_text("# Wiki Index\n\n", encoding="utf-8")

    def read_page(self, page_name: str) -> Optional[str]:
        path = self.wiki_dir / f"{page_name}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_page(self, page_name: str, content: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        path.write_text(content, encoding="utf-8")

    def delete_page(self, page_name: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        if path.exists():
            path.unlink()

    def list_pages(self) -> list[str]:
        return [
            p.stem for p in self.wiki_dir.glob("*.md")
            if p.stem != "index"
        ]

    def read_index(self) -> str:
        return (self.wiki_dir / "index.md").read_text(encoding="utf-8")

    def update_index(self, summaries: dict[str, str]) -> None:
        lines = ["# Wiki Index\n"]
        for page_name, summary in sorted(summaries.items()):
            lines.append(f"- **[{page_name}]({page_name}.md)** — {summary}")
        (self.wiki_dir / "index.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_store.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/wiki/__init__.py backend/tars/wiki/store.py backend/tests/test_wiki_store.py
git commit -m "feat(wiki): add WikiStore for markdown file storage"
```

---

## Task 2: WikiRagRouter — 路由判断层

**Files:**
- Create: `backend/tars/wiki/router.py`
- Create: `backend/tests/test_wiki_router.py`

- [ ] **Step 1: Write failing tests for WikiRagRouter**

```python
# backend/tests/test_wiki_router.py
import pytest
from unittest.mock import AsyncMock
from tars.wiki.router import WikiRagRouter


@pytest.fixture
def router():
    return WikiRagRouter(llm_provider=None)


def test_large_file_routes_to_rag(router):
    result = router.route(page_count=20, text_size=80000, file_name="report.pdf", file_format="pdf")
    assert result == "rag"


def test_small_markdown_routes_to_wiki(router):
    result = router.route(page_count=2, text_size=3000, file_name="notes.md", file_format="md")
    assert result == "wiki"


def test_meeting_minutes_routes_to_wiki(router):
    result = router.route(page_count=5, text_size=8000, file_name="2026-05-25-周例会纪要.md", file_format="md")
    assert result == "wiki"


def test_academic_paper_routes_to_rag(router):
    result = router.route(page_count=12, text_size=40000, file_name="paper.pdf", file_format="pdf", has_abstract=True)
    assert result == "rag"


def test_user_override_respected(router):
    result = router.route(page_count=100, text_size=200000, file_name="huge.pdf", file_format="pdf", user_override="wiki")
    assert result == "wiki"


def test_ambiguous_file_returns_llm_decide(router):
    result = router.route(page_count=8, text_size=25000, file_name="brief.pdf", file_format="pdf")
    assert result == "llm_decide"


@pytest.mark.asyncio
async def test_llm_fallback_decision():
    mock_llm = AsyncMock(return_value="wiki")
    router = WikiRagRouter(llm_provider=mock_llm)
    result = await router.route_with_llm_fallback(
        page_count=8, text_size=25000, file_name="brief.pdf",
        file_format="pdf", text_preview="行业简报：2026年Q2港口吞吐量..."
    )
    assert result in ("wiki", "rag")
    mock_llm.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_router.py -v`
Expected: FAIL — module `tars.wiki.router` not found

- [ ] **Step 3: Implement WikiRagRouter**

```python
# backend/tars/wiki/router.py
import re
from typing import Optional, Callable, Awaitable

MEETING_KEYWORDS = re.compile(r"(会议|纪要|meeting|minutes|周会|例会|晨会|站会)")


class WikiRagRouter:
    def __init__(self, llm_provider: Optional[Callable[..., Awaitable[str]]] = None):
        self.llm_provider = llm_provider

    def route(
        self,
        page_count: Optional[int] = None,
        text_size: int = 0,
        file_name: str = "",
        file_format: str = "",
        has_abstract: bool = False,
        user_override: Optional[str] = None,
    ) -> str:
        if user_override:
            return user_override

        if (page_count and page_count > 15) or text_size > 50000:
            return "rag"
        if has_abstract and file_format == "pdf":
            return "rag"
        if MEETING_KEYWORDS.search(file_name):
            return "wiki"
        if text_size < 10000 and file_format in ("md", "txt"):
            return "wiki"

        return "llm_decide"

    async def route_with_llm_fallback(
        self,
        page_count: Optional[int] = None,
        text_size: int = 0,
        file_name: str = "",
        file_format: str = "",
        has_abstract: bool = False,
        user_override: Optional[str] = None,
        text_preview: str = "",
    ) -> str:
        decision = self.route(
            page_count=page_count, text_size=text_size,
            file_name=file_name, file_format=file_format,
            has_abstract=has_abstract, user_override=user_override,
        )
        if decision != "llm_decide":
            return decision

        if not self.llm_provider:
            return "rag"

        prompt = (
            f"判断以下文件适合编译进结构化 wiki（适合综合归纳、频繁引用的内容）"
            f"还是作为 RAG 检索源保留原文（适合大文档、需要精确引用）。\n\n"
            f"文件名: {file_name}\n格式: {file_format}\n"
            f"页数: {page_count}\n文本量: {text_size} 字符\n"
            f"内容预览: {text_preview[:500]}\n\n"
            f"只回答 wiki 或 rag，不要解释。"
        )
        result = await self.llm_provider(prompt)
        return "wiki" if "wiki" in result.lower() else "rag"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_router.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/wiki/router.py backend/tests/test_wiki_router.py
git commit -m "feat(wiki): add WikiRagRouter with rule-based + LLM fallback routing"
```

---

## Task 3: WikiCompiler — LLM 编译引擎

**Files:**
- Create: `backend/tars/wiki/compiler.py`
- Create: `backend/tests/test_wiki_compiler.py`

- [ ] **Step 1: Write failing tests for WikiCompiler**

```python
# backend/tests/test_wiki_compiler.py
import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from tars.wiki.compiler import WikiCompiler
from tars.wiki.store import WikiStore


@pytest.fixture
def wiki_store(tmp_path):
    return WikiStore(wiki_dir=tmp_path)


@pytest.fixture
def compiler(wiki_store):
    mock_llm = AsyncMock()
    return WikiCompiler(store=wiki_store, llm_provider=mock_llm)


@pytest.mark.asyncio
async def test_compile_new_content_creates_page(compiler):
    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "port-ops", '
        '"content": "# 港口运营\\n\\n泊位A已分配给XX轮", '
        '"summary": "港口运营相关知识"}'
    )
    result = await compiler.compile(
        source_text="今天泊位A分配给了XX轮",
        source_label="2026-05-25 周例会",
    )
    assert result.page_name == "port-ops"
    assert result.action == "create"
    assert compiler.store.read_page("port-ops") is not None


@pytest.mark.asyncio
async def test_compile_update_existing_page(compiler):
    compiler.store.write_page("port-ops", "# 港口运营\n\n旧内容")
    compiler.llm_provider.return_value = (
        '{"action": "update", "page_name": "port-ops", '
        '"content": "# 港口运营\\n\\n旧内容\\n\\n新增：泊位B开放", '
        '"summary": "港口运营相关知识"}'
    )
    result = await compiler.compile(
        source_text="泊位B今天开放了",
        source_label="运营通知",
    )
    assert result.action == "update"
    content = compiler.store.read_page("port-ops")
    assert "泊位B" in content


@pytest.mark.asyncio
async def test_compile_updates_index(compiler):
    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "vessel-schedule", '
        '"content": "# 船舶调度\\n\\n内容", '
        '"summary": "船舶调度和排期信息"}'
    )
    await compiler.compile(source_text="XX轮明天到港", source_label="调度通知")
    index = compiler.store.read_index()
    assert "vessel-schedule" in index
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_compiler.py -v`
Expected: FAIL — module `tars.wiki.compiler` not found

- [ ] **Step 3: Implement WikiCompiler**

```python
# backend/tars/wiki/compiler.py
import json
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

from tars.wiki.store import WikiStore

logger = logging.getLogger(__name__)

COMPILE_PROMPT_TEMPLATE = """\
你是知识编辑者，负责将新素材整合进 wiki。

当前 wiki 索引：
{index}

当前已有页面列表：{pages}

新素材来源：{source_label}
新素材内容：
{source_text}

请决定如何处理这段素材。返回 JSON（不要 markdown 代码块）：
{{
  "action": "create" 或 "update",
  "page_name": "页面文件名（英文短横线命名）",
  "content": "完整的页面 Markdown 内容（如果 update 则包含合并后的完整内容）",
  "summary": "一句话描述这个页面的内容（用于 index）"
}}

规则：
- 如果素材属于已有页面的主题，选择 update 并合并内容
- 如果是全新主题，选择 create
- 页面内容要结构化、有标题层级
- 在页面末尾的"来源追溯"段落记录本次更新来源
"""


@dataclass
class CompileResult:
    action: str
    page_name: str
    summary: str


class WikiCompiler:
    def __init__(self, store: WikiStore, llm_provider: Callable[..., Awaitable[str]]):
        self.store = store
        self.llm_provider = llm_provider

    async def compile(self, source_text: str, source_label: str) -> CompileResult:
        index = self.store.read_index()
        pages = self.store.list_pages()

        prompt = COMPILE_PROMPT_TEMPLATE.format(
            index=index,
            pages=", ".join(pages) if pages else "(空)",
            source_label=source_label,
            source_text=source_text[:3000],
        )

        raw = await self.llm_provider(prompt)
        data = json.loads(raw)

        self.store.write_page(data["page_name"], data["content"])

        # Rebuild index with all page summaries
        all_summaries = {}
        for p in self.store.list_pages():
            all_summaries[p] = data["summary"] if p == data["page_name"] else p
        # Preserve existing summaries from index
        self._merge_index_summaries(all_summaries, data["page_name"], data["summary"])

        return CompileResult(
            action=data["action"],
            page_name=data["page_name"],
            summary=data["summary"],
        )

    def _merge_index_summaries(self, summaries: dict, new_page: str, new_summary: str) -> None:
        existing_index = self.store.read_index()
        for line in existing_index.splitlines():
            if line.startswith("- **["):
                # Parse: - **[name](name.md)** — summary
                try:
                    name = line.split("[")[1].split("]")[0]
                    summary = line.split("—")[-1].strip()
                    if name != new_page:
                        summaries[name] = summary
                except (IndexError, ValueError):
                    pass
        summaries[new_page] = new_summary
        self.store.update_index(summaries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_compiler.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/wiki/compiler.py backend/tests/test_wiki_compiler.py
git commit -m "feat(wiki): add WikiCompiler for LLM-driven incremental compilation"
```

---

## Task 4: read_wiki 工具

**Files:**
- Create: `backend/tars/tools/builtin/wiki_read.py`
- Create: `backend/tests/test_wiki_read_tool.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_wiki_read_tool.py
import pytest
from pathlib import Path
from tars.wiki.store import WikiStore
from tars.tools.builtin.wiki_read import WikiReadTool


@pytest.fixture
def wiki_store(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营\n\n泊位分配规则...")
    store.update_index({"port-ops": "港口运营相关知识"})
    return store


@pytest.fixture
def tool(wiki_store):
    return WikiReadTool(store=wiki_store)


@pytest.mark.asyncio
async def test_read_existing_page(tool):
    result = await tool.execute(page_name="port-ops")
    assert result.success
    assert "港口运营" in result.output


@pytest.mark.asyncio
async def test_read_nonexistent_page(tool):
    result = await tool.execute(page_name="nonexistent")
    assert not result.success
    assert "不存在" in result.output


@pytest.mark.asyncio
async def test_read_index(tool):
    result = await tool.execute(page_name="index")
    assert result.success
    assert "port-ops" in result.output


def test_tool_schema(tool):
    schema = tool.to_function_schema()
    assert schema["name"] == "read_wiki"
    assert "page_name" in schema["parameters"]["properties"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_read_tool.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement WikiReadTool**

```python
# backend/tars/tools/builtin/wiki_read.py
from tars.tools.base import BaseTool, ToolResult
from tars.wiki.store import WikiStore


class WikiReadTool(BaseTool):
    name: str = "read_wiki"
    description: str = "读取 wiki 中指定页面的完整内容。传入 page_name 获取具体页面，传入 'index' 获取所有页面索引。"
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "page_name": {
                "type": "string",
                "description": "要读取的 wiki 页面名称，或 'index' 获取索引",
            },
        },
        "required": ["page_name"],
    }

    def __init__(self, store: WikiStore):
        self.store = store

    async def execute(self, **kwargs) -> ToolResult:
        page_name = kwargs.get("page_name", "index")

        if page_name == "index":
            content = self.store.read_index()
            return ToolResult(success=True, output=content)

        content = self.store.read_page(page_name)
        if content is None:
            pages = self.store.list_pages()
            return ToolResult(
                success=False,
                output=f"页面 '{page_name}' 不存在。可用页面: {', '.join(pages)}",
            )
        return ToolResult(success=True, output=content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_read_tool.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/tools/builtin/wiki_read.py backend/tests/test_wiki_read_tool.py
git commit -m "feat(wiki): add read_wiki tool for agent wiki access"
```

---

## Task 5: Wiki API 端点

**Files:**
- Create: `backend/tars/api/wiki.py`
- Create: `backend/tests/test_wiki_api.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_wiki_api.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI
from tars.wiki.store import WikiStore
from tars.api.wiki import create_wiki_router


@pytest.fixture
def app(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营\n\n内容")
    store.update_index({"port-ops": "港口运营相关知识"})
    app = FastAPI()
    app.include_router(create_wiki_router(store), prefix="/api/wiki")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_pages(client):
    resp = client.get("/api/wiki/")
    assert resp.status_code == 200
    data = resp.json()
    assert "port-ops" in [p["name"] for p in data["pages"]]


def test_get_page(client):
    resp = client.get("/api/wiki/port-ops")
    assert resp.status_code == 200
    assert "港口运营" in resp.json()["content"]


def test_get_nonexistent_page(client):
    resp = client.get("/api/wiki/nonexistent")
    assert resp.status_code == 404


def test_update_page(client):
    resp = client.put("/api/wiki/port-ops", json={"content": "# 港口运营\n\n更新内容"})
    assert resp.status_code == 200
    resp2 = client.get("/api/wiki/port-ops")
    assert "更新内容" in resp2.json()["content"]


def test_delete_page(client):
    resp = client.delete("/api/wiki/port-ops")
    assert resp.status_code == 200
    resp2 = client.get("/api/wiki/port-ops")
    assert resp2.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_api.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Wiki API**

```python
# backend/tars/api/wiki.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from tars.wiki.store import WikiStore


class PageUpdateRequest(BaseModel):
    content: str


def create_wiki_router(store: WikiStore) -> APIRouter:
    router = APIRouter(tags=["wiki"])

    @router.get("/")
    def list_pages():
        pages = store.list_pages()
        return {
            "pages": [
                {"name": p, "url": f"/api/wiki/{p}"}
                for p in sorted(pages)
            ]
        }

    @router.get("/{page_name}")
    def get_page(page_name: str):
        if page_name == "index":
            return {"content": store.read_index()}
        content = store.read_page(page_name)
        if content is None:
            raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
        return {"name": page_name, "content": content}

    @router.put("/{page_name}")
    def update_page(page_name: str, req: PageUpdateRequest):
        store.write_page(page_name, req.content)
        return {"success": True, "name": page_name}

    @router.delete("/{page_name}")
    def delete_page(page_name: str):
        if store.read_page(page_name) is None:
            raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
        store.delete_page(page_name)
        return {"success": True}

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/api/wiki.py backend/tests/test_wiki_api.py
git commit -m "feat(wiki): add Wiki CRUD REST API"
```

---

## Task 6: System Prompt 注入 Wiki Index

**Files:**
- Modify: `backend/tars/agent/agent.py` (在 `_build_static_prompt` 中注入 wiki index)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_wiki_prompt_injection.py
import pytest
from pathlib import Path
from tars.wiki.store import WikiStore


def test_wiki_index_injection_format(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营")
    store.update_index({"port-ops": "港口运营相关知识"})

    index_content = store.read_index()
    # Verify the format is suitable for prompt injection
    assert "port-ops" in index_content
    assert len(index_content) < 5000  # Reasonable size for prompt
```

- [ ] **Step 2: Run test to verify it passes** (this validates the format)

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_prompt_injection.py -v`
Expected: PASS

- [ ] **Step 3: Modify agent.py to inject wiki index**

In `backend/tars/agent/agent.py`, locate `_build_static_prompt` method (around line 938). After the knowledge base rules section (line ~981), add:

```python
# Wiki index injection
if self.wiki_store:
    wiki_index = self.wiki_store.read_index()
    if wiki_index.strip() and wiki_index != "# Wiki Index\n\n":
        parts.append(
            "\n## 你的知识 Wiki\n"
            "以下是你维护的结构化知识库索引，需要详细信息时使用 read_wiki 工具查阅具体页面：\n\n"
            f"{wiki_index}\n"
        )
```

In `AgentV2.__init__`, add parameter:

```python
self.wiki_store: Optional[WikiStore] = kwargs.get("wiki_store")
```

- [ ] **Step 4: Run existing agent tests to verify no regression**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -k "agent" -v --timeout=30`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/agent/agent.py backend/tests/test_wiki_prompt_injection.py
git commit -m "feat(wiki): inject wiki index into agent system prompt"
```

---

## Task 7: 路由集成 — 上传入口扩展

**Files:**
- Modify: `backend/tars/api/knowledge.py` (扩展 upload endpoint)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_wiki_upload_routing.py
import pytest
from tars.wiki.router import WikiRagRouter


def test_upload_routing_integration():
    router = WikiRagRouter(llm_provider=None)

    # Simulate various upload scenarios
    assert router.route(page_count=3, text_size=2000, file_name="周例会纪要.md", file_format="md") == "wiki"
    assert router.route(page_count=50, text_size=100000, file_name="industry-report.pdf", file_format="pdf") == "rag"
    assert router.route(page_count=1, text_size=500, file_name="quick-note.txt", file_format="txt") == "wiki"
    assert router.route(page_count=12, text_size=45000, file_name="paper.pdf", file_format="pdf", has_abstract=True) == "rag"
```

- [ ] **Step 2: Run test**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_upload_routing.py -v`
Expected: PASS (uses already-implemented router)

- [ ] **Step 3: Modify knowledge.py upload endpoint**

In `backend/tars/api/knowledge.py`, modify the document upload endpoint to accept a `target` query param and route accordingly:

```python
# Add to upload endpoint parameters
from tars.wiki.router import WikiRagRouter

# In the upload handler, after file parsing:
target: str = Query(default="auto", regex="^(auto|wiki|rag)$")

# Route decision
wiki_router = WikiRagRouter(llm_provider=None)  # initialized at module level
route_decision = wiki_router.route(
    page_count=parsed.page_count,
    text_size=len(parsed.full_text),
    file_name=file.filename,
    file_format=file_ext,
    user_override=target if target != "auto" else None,
)

if route_decision == "wiki":
    # Schedule wiki compilation instead of RAG ingestion
    _schedule_wiki_compile(parsed.full_text, file.filename, wiki_compiler)
    return {"success": True, "routed_to": "wiki", "route_reason": "..."}
else:
    # Existing RAG pipeline
    _schedule_ingest(...)
    return {"success": True, "routed_to": "rag", ...}
```

- [ ] **Step 4: Run full knowledge API tests**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -k "knowledge" -v --timeout=30`
Expected: All existing tests PASS + new routing test PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/api/knowledge.py backend/tests/test_wiki_upload_routing.py
git commit -m "feat(wiki): integrate wiki routing into unified upload endpoint"
```

---

## Task 8: 事件驱动 — 会议结束触发编译

**Files:**
- Modify: `backend/tars/api/knowledge.py` or meeting module (wherever meeting_ended event is handled)
- Create: `backend/tars/wiki/events.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_wiki_events.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from tars.wiki.events import WikiEventHandler
from tars.wiki.compiler import WikiCompiler
from tars.wiki.store import WikiStore


@pytest.fixture
def handler(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    mock_llm = AsyncMock(return_value=(
        '{"action": "create", "page_name": "meeting-0525", '
        '"content": "# 会议纪要 2026-05-25\\n\\n决策要点...", '
        '"summary": "2026-05-25 周例会纪要"}'
    ))
    compiler = WikiCompiler(store=store, llm_provider=mock_llm)
    return WikiEventHandler(compiler=compiler)


@pytest.mark.asyncio
async def test_on_meeting_ended(handler):
    await handler.on_meeting_ended(
        transcript="今天讨论了泊位分配问题，决定A泊位给XX轮...",
        meeting_title="2026-05-25 周例会",
    )
    page = handler.compiler.store.read_page("meeting-0525")
    assert page is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_events.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement WikiEventHandler**

```python
# backend/tars/wiki/events.py
import logging
from tars.wiki.compiler import WikiCompiler

logger = logging.getLogger(__name__)


class WikiEventHandler:
    def __init__(self, compiler: WikiCompiler):
        self.compiler = compiler

    async def on_meeting_ended(self, transcript: str, meeting_title: str) -> None:
        logger.info(f"Wiki compile triggered: meeting ended — {meeting_title}")
        await self.compiler.compile(
            source_text=transcript,
            source_label=meeting_title,
        )

    async def on_small_file_uploaded(self, text: str, file_name: str) -> None:
        logger.info(f"Wiki compile triggered: file upload — {file_name}")
        await self.compiler.compile(
            source_text=text,
            source_label=f"文件上传: {file_name}",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/test_wiki_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tars/wiki/events.py backend/tests/test_wiki_events.py
git commit -m "feat(wiki): add event-driven wiki compilation triggers"
```

---

## Task 9: main.py 初始化集成

**Files:**
- Modify: `backend/tars/main.py`

- [ ] **Step 1: Add wiki initialization to main.py**

After the knowledge system initialization (around line 385), add:

```python
# Wiki system initialization
from tars.wiki.store import WikiStore
from tars.wiki.compiler import WikiCompiler
from tars.wiki.events import WikiEventHandler
from tars.tools.builtin.wiki_read import WikiReadTool
from tars.api.wiki import create_wiki_router

wiki_dir = Path(data_dir) / "wiki"
wiki_store = WikiStore(wiki_dir=wiki_dir)

async def _wiki_llm_call(prompt: str) -> str:
    resp = await llm_provider.complete(prompt, max_tokens=2000)
    return resp.content

wiki_compiler = WikiCompiler(store=wiki_store, llm_provider=_wiki_llm_call)
wiki_event_handler = WikiEventHandler(compiler=wiki_compiler)

# Register wiki tool
tool_registry.register(WikiReadTool(store=wiki_store))

# Register wiki API
app.include_router(create_wiki_router(wiki_store), prefix="/api/wiki")

# Pass wiki_store to agent
# (add wiki_store=wiki_store to AgentV2 constructor call)
```

- [ ] **Step 2: Verify server starts without errors**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -c "from tars.wiki.store import WikiStore; from tars.wiki.compiler import WikiCompiler; from tars.wiki.events import WikiEventHandler; from tars.tools.builtin.wiki_read import WikiReadTool; from tars.api.wiki import create_wiki_router; print('All imports OK')"`
Expected: "All imports OK"

- [ ] **Step 3: Commit**

```bash
git add backend/tars/main.py
git commit -m "feat(wiki): wire up wiki system in main.py initialization"
```

---

## Task 10: 前端 Wiki Tab

**Files:**
- Create: `frontend/src/components/knowledge/WikiViewer.vue`
- Modify: `frontend/src/components/knowledge/KnowledgeManager.vue` (添加 tab)

- [ ] **Step 1: Create WikiViewer component**

```vue
<!-- frontend/src/components/knowledge/WikiViewer.vue -->
<template>
  <div class="wiki-viewer">
    <div class="wiki-sidebar">
      <h3>{{ $t('wiki.title', 'Wiki') }}</h3>
      <ul class="wiki-page-list">
        <li
          v-for="page in pages"
          :key="page.name"
          :class="{ active: page.name === activePage }"
          @click="loadPage(page.name)"
        >
          {{ page.name }}
        </li>
      </ul>
    </div>
    <div class="wiki-content">
      <div v-if="loading" class="wiki-loading">Loading...</div>
      <div v-else-if="content" class="wiki-markdown" v-html="renderedContent" />
      <div v-else class="wiki-empty">{{ $t('wiki.selectPage', '选择一个页面查看') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'

const pages = ref<{ name: string }[]>([])
const activePage = ref('')
const content = ref('')
const loading = ref(false)

const renderedContent = computed(() => content.value ? marked(content.value) : '')

async function fetchPages() {
  const resp = await fetch('/api/wiki/')
  const data = await resp.json()
  pages.value = data.pages
}

async function loadPage(name: string) {
  activePage.value = name
  loading.value = true
  const resp = await fetch(`/api/wiki/${name}`)
  const data = await resp.json()
  content.value = data.content
  loading.value = false
}

onMounted(fetchPages)
</script>

<style scoped>
.wiki-viewer { display: flex; height: 100%; }
.wiki-sidebar { width: 200px; border-right: 1px solid var(--border-color); padding: 1rem; overflow-y: auto; }
.wiki-page-list { list-style: none; padding: 0; }
.wiki-page-list li { padding: 0.5rem; cursor: pointer; border-radius: 4px; }
.wiki-page-list li.active { background: var(--bg-active); }
.wiki-content { flex: 1; padding: 1rem; overflow-y: auto; }
</style>
```

- [ ] **Step 2: Add Wiki tab to KnowledgeManager.vue**

In `frontend/src/components/knowledge/KnowledgeManager.vue`, add a tab for Wiki alongside the existing knowledge tab:

```vue
<!-- Add to template tabs section -->
<el-tab-pane label="Wiki" name="wiki">
  <WikiViewer />
</el-tab-pane>
```

```typescript
// Add to imports
import WikiViewer from './WikiViewer.vue'
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge/WikiViewer.vue frontend/src/components/knowledge/KnowledgeManager.vue
git commit -m "feat(wiki): add Wiki tab with page viewer in frontend"
```

---

## Task 11: 端到端验证

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/daobanxiang/myproject/TARS/backend && python -m pytest tests/ -v --timeout=60`
Expected: All tests PASS

- [ ] **Step 2: Manual smoke test**

1. Start backend: `cd backend && python -m uvicorn tars.main:app --reload`
2. Upload a small markdown file via `/api/knowledge/upload?target=wiki`
3. Verify it appears in `/api/wiki/`
4. Call `read_wiki` tool via agent conversation
5. Check wiki index is in system prompt

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix(wiki): address integration issues from e2e testing"
```
