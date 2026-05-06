# 记忆系统 V3（Letta 混合模式）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写记忆系统为 Letta 混合模式 — 4 块自编辑 core memory + archival memory + Ebbinghaus 软衰减 + Web 搜索沉淀。

**Architecture:** Core memory（4 块固定区块，注入 system prompt）由 Agent 通过 4 个工具自主编辑；后处理 reflector LLM 每轮兜底更新；archival memory 用衰减算法排序检索；web 工具结果通过 reflector 沉淀。

**Tech Stack:** Python 3.14, SQLite (FTS5 + BLOB), sentence-transformers (bge-small-zh-v1.5), pytest-asyncio, Ollama function calling。

**Reference Spec:** [docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md](../specs/2026-05-06-memory-v3-letta-design.md)

---

## 文件结构

新增/修改：

```
backend/tars/memory/
├── __init__.py           (修改) 导出新接口
├── core_memory.py        (新) CoreMemoryManager + 4 个 BaseTool
├── reflector.py          (新) Reflector LLM
├── decay.py              (新) Ebbinghaus 衰减评分
├── archival.py           (新) ArchivalManager
├── manager.py            (重写) 整合 core + archival + reflector
├── search.py             (修改) 集成 decay 评分
├── extractor.py          (保留)
├── deduplicator.py       (保留)
└── embeddings.py         (不变)

backend/tars/database/base.py  (修改) 加表加列
backend/tars/main.py            (修改) 注册 core memory 工具
backend/tars/agent/agent.py     (修改) system prompt 注入 + 异步 reflect
backend/tests/test_memory_v3.py (新)
```

---

## Task 1: 数据库 schema 迁移

**Files:**
- Modify: `backend/tars/database/base.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — core_memory_blocks 表存在且默认 4 行**

`backend/tests/test_memory_v3.py`:
```python
"""TARS Memory V3 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestSchemaMigration:
    def test_core_memory_blocks_table(self, tmp_path):
        from tars.database import Database
        db_path = str(tmp_path / "test.db")
        db = Database(db_path=db_path)
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM core_memory_blocks ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        assert names == ["persona", "project_context", "user_profile", "working_principles"]

    def test_memories_has_access_count_and_source(self, tmp_path):
        from tars.database import Database
        db = Database(db_path=str(tmp_path / "test.db"))
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(memories)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "access_count" in cols
        assert "source" in cols
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestSchemaMigration -v
```
预期：FAIL（表不存在 / 列不存在）

- [ ] **Step 3: 在 Database._init_schema 加 core_memory_blocks 表与默认数据**

修改 `backend/tars/database/base.py`，在 `memories` 表创建之后、`memories_fts` 之前加入：

```python
# core memory 4 块固定区块（Letta 模式）
cursor.execute("""
    CREATE TABLE IF NOT EXISTS core_memory_blocks (
        name TEXT PRIMARY KEY,
        content TEXT NOT NULL DEFAULT '',
        updated_at TEXT
    )
""")

DEFAULT_BLOCKS = {
    "persona": "TARS：理性、简洁、注重证据的工程助手。回答以代码/事实为主，避免空话。",
    "user_profile": "（暂未学习到用户信息）",
    "project_context": "（暂未记录项目上下文）",
    "working_principles": "（暂未累积协作准则）",
}
now_str = get_local_now().isoformat() if hasattr(get_local_now(), "isoformat") else str(get_local_now())
for name, content in DEFAULT_BLOCKS.items():
    cursor.execute(
        "INSERT OR IGNORE INTO core_memory_blocks (name, content, updated_at) VALUES (?, ?, ?)",
        (name, content, now_str),
    )

# memories 表迁移：access_count + source
for col_def in [
    ("access_count", "INTEGER DEFAULT 0"),
    ("source", "TEXT DEFAULT 'conversation'"),
]:
    try:
        cursor.execute(f"ALTER TABLE memories ADD COLUMN {col_def[0]} {col_def[1]}")
    except sqlite3.OperationalError:
        pass
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestSchemaMigration -v
```
预期：PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add tars/database/base.py tests/test_memory_v3.py 2>/dev/null || true
echo "Task 1 done"  # 项目不是 git 仓库则跳过 git
```

---

## Task 2: CoreMemoryManager 基础读写

**Files:**
- Create: `backend/tars/memory/core_memory.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — get/replace/append 行为**

追加到 `tests/test_memory_v3.py`:
```python
class TestCoreMemoryManager:
    def test_get_default(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        assert "TARS" in cm.get("persona")
        assert cm.get("nonexistent") == ""

    def test_replace(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        ok = cm.replace("user_profile", "old", "用户：张三")
        # 默认值不含 "old"，replace 行为应直接覆盖
        cm.set("user_profile", "用户喜欢 Python")
        ok = cm.replace("user_profile", "Python", "Go")
        assert ok is True
        assert "Go" in cm.get("user_profile")

    def test_append(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("working_principles", "")
        cm.append("working_principles", "不要主动改文档")
        cm.append("working_principles", "commit 前必须问")
        content = cm.get("working_principles")
        assert "不要主动改文档" in content
        assert "commit 前必须问" in content

    def test_trim_when_oversized(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db, max_size=100)
        cm.set("persona", "")
        for i in range(50):
            cm.append("persona", f"line {i} 占位文本占位文本")
        content = cm.get("persona")
        assert len(content.encode("utf-8")) <= 100
        # 应保留最新内容
        assert "line 49" in content

    def test_render_for_prompt(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("persona", "TARS")
        cm.set("user_profile", "用户 A")
        rendered = cm.render_for_prompt()
        assert "## 核心记忆" in rendered
        assert "### Persona" in rendered
        assert "TARS" in rendered
        assert "### User Profile" in rendered
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestCoreMemoryManager -v
```
预期：FAIL（模块不存在）

- [ ] **Step 3: 实现 CoreMemoryManager**

创建 `backend/tars/memory/core_memory.py`:
```python
"""Core Memory — Letta 模式的 4 块固定区块管理"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


BLOCK_NAMES = ["persona", "user_profile", "project_context", "working_principles"]
BLOCK_TITLES = {
    "persona": "Persona",
    "user_profile": "User Profile",
    "project_context": "Project Context",
    "working_principles": "Working Principles",
}


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class CoreMemoryManager:
    """4 块固定区块的读写 + 自动 trim"""

    def __init__(self, db, max_size: int = 2048):
        self.db = db
        self.max_size = max_size

    def get(self, block: str) -> str:
        if block not in BLOCK_NAMES:
            return ""
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT content FROM core_memory_blocks WHERE name = ?", (block,))
        row = cur.fetchone()
        return row[0] if row else ""

    def get_all(self) -> Dict[str, str]:
        return {name: self.get(name) for name in BLOCK_NAMES}

    def set(self, block: str, content: str) -> bool:
        if block not in BLOCK_NAMES:
            return False
        content = self._trim(content)
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE core_memory_blocks SET content = ?, updated_at = ? WHERE name = ?",
            (content, _now_iso(), block),
        )
        conn.commit()
        return True

    def append(self, block: str, content: str) -> bool:
        current = self.get(block)
        sep = "\n" if current and not current.endswith("\n") else ""
        new = current + sep + content.strip()
        return self.set(block, new)

    def replace(self, block: str, old: str, new: str) -> bool:
        current = self.get(block)
        if old in current:
            updated = current.replace(old, new, 1)
        else:
            updated = (current + ("\n" if current else "") + new).strip()
        return self.set(block, updated)

    def render_for_prompt(self) -> str:
        parts = ["## 核心记忆"]
        for name in BLOCK_NAMES:
            content = self.get(name).strip()
            if not content:
                continue
            parts.append(f"\n### {BLOCK_TITLES[name]}\n{content}")
        return "\n".join(parts)

    def _trim(self, content: str) -> str:
        encoded = content.encode("utf-8")
        if len(encoded) <= self.max_size:
            return content
        # 从开头删除最旧的行直到落在大小内
        lines = content.split("\n")
        while lines and len("\n".join(lines).encode("utf-8")) > self.max_size:
            lines.pop(0)
        if not lines:
            # 单行超长 → 截断尾部
            return content.encode("utf-8")[-self.max_size:].decode("utf-8", errors="ignore")
        return "\n".join(lines)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestCoreMemoryManager -v
```
预期：PASS（5/5）

- [ ] **Step 5: 提交**

```bash
cd backend && echo "Task 2 done — CoreMemoryManager 实现完成"
```

---

## Task 3: Core Memory 编辑工具（暴露给 Agent）

**Files:**
- Modify: `backend/tars/memory/core_memory.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — 4 个工具的 BaseTool 接口**

追加到 `tests/test_memory_v3.py`:
```python
class TestCoreMemoryTools:
    @pytest.mark.asyncio
    async def test_append_tool(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryAppendTool
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("user_profile", "")
        tool = CoreMemoryAppendTool(cm)
        result = await tool.execute(block="user_profile", content="用户使用 Mac M1")
        assert result.success is True
        assert "Mac M1" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_replace_tool(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryReplaceTool
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        cm.set("user_profile", "用户使用 Python")
        tool = CoreMemoryReplaceTool(cm)
        result = await tool.execute(block="user_profile", old="Python", new="Go")
        assert result.success is True
        assert "Go" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_invalid_block_rejected(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager, CoreMemoryAppendTool
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        tool = CoreMemoryAppendTool(cm)
        result = await tool.execute(block="invalid_block", content="x")
        assert result.success is False
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestCoreMemoryTools -v
```
预期：FAIL（工具类不存在）

- [ ] **Step 3: 在 core_memory.py 末尾追加工具类**

追加到 `backend/tars/memory/core_memory.py`:
```python
from typing import Any, Dict
from ..tools.base import BaseTool, ToolResult


class CoreMemoryAppendTool(BaseTool):
    name: str = "core_memory_append"
    description: str = (
        "追加内容到指定的 core memory 区块。用于记录新学到的用户信息、项目上下文、协作准则等。"
        "区块名必须是 persona / user_profile / project_context / working_principles 之一。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "block": {"type": "string", "enum": BLOCK_NAMES, "description": "区块名"},
            "content": {"type": "string", "description": "要追加的内容（一行简洁事实）"},
        },
        "required": ["block", "content"],
    }

    def __init__(self, manager: CoreMemoryManager):
        self.manager = manager

    async def execute(self, **kwargs) -> ToolResult:
        block = kwargs.get("block", "")
        content = kwargs.get("content", "").strip()
        if block not in BLOCK_NAMES:
            return ToolResult(success=False, output="", error=f"无效的区块名: {block}")
        if not content:
            return ToolResult(success=False, output="", error="content 不能为空")
        ok = self.manager.append(block, content)
        if ok:
            return ToolResult(success=True, output=f"已追加到 {block}: {content[:50]}")
        return ToolResult(success=False, output="", error="追加失败")


class CoreMemoryReplaceTool(BaseTool):
    name: str = "core_memory_replace"
    description: str = (
        "替换指定 core memory 区块中的某段文本。用于修正用户信息、更新项目状态等。"
        "若 old 不存在则等同于追加 new。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "block": {"type": "string", "enum": BLOCK_NAMES},
            "old": {"type": "string", "description": "要被替换的旧文本"},
            "new": {"type": "string", "description": "新文本"},
        },
        "required": ["block", "old", "new"],
    }

    def __init__(self, manager: CoreMemoryManager):
        self.manager = manager

    async def execute(self, **kwargs) -> ToolResult:
        block = kwargs.get("block", "")
        old = kwargs.get("old", "")
        new = kwargs.get("new", "")
        if block not in BLOCK_NAMES:
            return ToolResult(success=False, output="", error=f"无效的区块名: {block}")
        ok = self.manager.replace(block, old, new)
        if ok:
            return ToolResult(success=True, output=f"已更新 {block}")
        return ToolResult(success=False, output="", error="替换失败")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestCoreMemoryTools -v
```
预期：PASS（3/3）

- [ ] **Step 5: 提交**

```bash
cd backend && echo "Task 3 done — Core Memory 工具实现完成"
```

---

## Task 4: Ebbinghaus 衰减评分

**Files:**
- Create: `backend/tars/memory/decay.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — 衰减分数的关键性质**

追加到 `tests/test_memory_v3.py`:
```python
class TestDecay:
    def test_recent_higher_than_old(self):
        from tars.memory.decay import decay_score
        recent_score = decay_score(similarity=0.7, importance=0.5, age_hours=1)
        old_score = decay_score(similarity=0.7, importance=0.5, age_hours=720)
        assert recent_score > old_score

    def test_high_importance_decays_slower(self):
        from tars.memory.decay import decay_score
        high = decay_score(similarity=0.7, importance=0.9, age_hours=720)
        low = decay_score(similarity=0.7, importance=0.2, age_hours=720)
        assert high > low

    def test_score_bounded(self):
        from tars.memory.decay import decay_score
        score = decay_score(similarity=1.0, importance=1.0, age_hours=0)
        assert 0 <= score <= 1.0001  # 允许浮点误差
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestDecay -v
```
预期：FAIL

- [ ] **Step 3: 实现 decay 模块**

创建 `backend/tars/memory/decay.py`:
```python
"""Ebbinghaus 衰减评分"""
import math
from datetime import datetime, timezone, timedelta


def decay_score(similarity: float, importance: float, age_hours: float) -> float:
    """
    检索综合分 = 相似度 * 0.6 + 衰减 * 0.2 + 重要性 * 0.2
    importance 越高半衰期越长（importance=1 时半衰期 720h ≈ 30 天）。
    """
    importance = max(min(importance, 1.0), 0.0)
    half_life = max(importance, 0.1) * 720
    decay = math.exp(-max(age_hours, 0) / half_life)
    return similarity * 0.6 + decay * 0.2 + importance * 0.2


def hours_since(timestamp_iso: str) -> float:
    """计算 ISO 时间戳到现在的小时数；解析失败返回 0"""
    if not timestamp_iso:
        return 0.0
    try:
        ts = datetime.fromisoformat(timestamp_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone(timedelta(hours=8)))
        now = datetime.now(timezone(timedelta(hours=8)))
        return max((now - ts).total_seconds() / 3600, 0.0)
    except (ValueError, TypeError):
        return 0.0
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestDecay -v
```
预期：PASS

- [ ] **Step 5: 提交**

```bash
cd backend && echo "Task 4 done — Decay 评分实现完成"
```

---

## Task 5: ArchivalManager + 强化机制

**Files:**
- Create: `backend/tars/memory/archival.py`
- Modify: `backend/tars/database/base.py`（添加强化方法）
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — insert + reinforce**

追加到 `tests/test_memory_v3.py`:
```python
class TestArchival:
    @pytest.mark.asyncio
    async def test_insert_with_source(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        mem = await am.insert(
            content="用户使用 Mac M1",
            category="fact",
            importance=0.7,
            source="conversation",
        )
        assert mem is not None
        assert mem.id

    @pytest.mark.asyncio
    async def test_reinforce(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        mem = await am.insert(content="测试事实", category="fact", importance=0.5, source="conversation")
        am.reinforce(mem.id)
        am.reinforce(mem.id)
        # 重新读取应看到 access_count >= 2 且 importance 微增
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT access_count, importance FROM memories WHERE id = ?", (mem.id,))
        row = cur.fetchone()
        assert row[0] >= 2
        assert row[1] > 0.5

    @pytest.mark.asyncio
    async def test_dedup_skips_duplicate(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        m1 = await am.insert(content="用户使用 Python", category="fact", importance=0.5, source="conversation")
        m2 = await am.insert(content="用户使用 Python", category="fact", importance=0.5, source="conversation")
        assert m1 is not None
        # 完全重复应返回 None
        assert m2 is None
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestArchival -v
```
预期：FAIL

- [ ] **Step 3: 在 Database 加入 add_memory 的 source 参数和 reinforce_memory 方法**

定位 `backend/tars/database/base.py:249` 的 `add_memory` 方法，修改签名和 SQL：

```python
def add_memory(
    self,
    content: str,
    category: str = "general",
    importance: float = 0.5,
    embedding: Optional[bytes] = None,
    source: str = "conversation",
) -> Memory:
    memory_id = str(uuid.uuid4())
    now = get_local_now()

    conn = self._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (id, content, category, importance, created_at, updated_at, last_accessed, embedding, access_count, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
        (memory_id, content, category, importance, now, now, None, embedding, source),
    )
    cursor.execute(
        "INSERT INTO memories_fts(rowid, content, category) VALUES (last_insert_rowid(), ?, ?)",
        (content, category),
    )
    conn.commit()
    return Memory(
        id=memory_id,
        content=content,
        category=category,
        importance=importance,
        created_at=now,
        updated_at=now,
    )

def reinforce_memory(self, memory_id: str, importance_delta: float = 0.02):
    """命中召回：access_count+1, last_accessed=now, importance 微增"""
    conn = self._get_conn()
    cursor = conn.cursor()
    now = get_local_now()
    cursor.execute(
        """
        UPDATE memories
        SET access_count = COALESCE(access_count, 0) + 1,
            last_accessed = ?,
            importance = MIN(1.0, COALESCE(importance, 0.5) + ?)
        WHERE id = ?
        """,
        (now, importance_delta, memory_id),
    )
    conn.commit()

def get_all_memories_with_metadata(self):
    """返回 (Memory, embedding_blob, last_accessed_iso, importance, source) 列表"""
    conn = self._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, content, category, importance, created_at, updated_at, embedding, last_accessed, source FROM memories"
    )
    results = []
    for row in cursor.fetchall():
        mem = Memory(
            id=row[0], content=row[1], category=row[2], importance=row[3],
            created_at=row[4], updated_at=row[5],
        )
        last_accessed_str = str(row[7]) if row[7] else ""
        results.append((mem, row[6], last_accessed_str, row[3] or 0.5, row[8] or "conversation"))
    return results
```

- [ ] **Step 4: 创建 ArchivalManager**

创建 `backend/tars/memory/archival.py`:
```python
"""Archival Memory — 长期记忆管理（写入 + 去重 + 强化）"""
from typing import Optional

from .deduplicator import MemoryDeduplicator
from .embeddings import EmbeddingProvider, serialize_vector


class ArchivalManager:
    """长期记忆写入器"""

    def __init__(self, db, embedding_provider: Optional[EmbeddingProvider] = None):
        self.db = db
        self.embedding_provider = embedding_provider
        self.deduplicator = MemoryDeduplicator(embedding_provider)

    async def insert(
        self,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
        source: str = "conversation",
    ):
        """写入新记忆。重复 → 返回 None；包含 → 更新旧记忆并返回更新后的对象"""
        content = content.strip()
        if not content or len(content) < 5:
            return None

        existing = self.db.get_recent_memories(50)
        is_dup, update_target = self.deduplicator.is_duplicate(content, existing)

        if is_dup and not update_target:
            return None

        if is_dup and update_target:
            self.db.update_memory(update_target.id, content=content)
            return update_target

        embedding_blob = None
        if self.embedding_provider:
            try:
                vec = self.embedding_provider.encode([content])[0]
                embedding_blob = serialize_vector(vec)
            except Exception as e:
                print(f"[ArchivalManager] 嵌入生成失败: {e}")

        return self.db.add_memory(
            content=content,
            category=category,
            importance=importance,
            embedding=embedding_blob,
            source=source,
        )

    def reinforce(self, memory_id: str):
        self.db.reinforce_memory(memory_id)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestArchival -v
```
预期：PASS（3/3）

- [ ] **Step 6: 提交**

```bash
cd backend && echo "Task 5 done — ArchivalManager 实现完成"
```

---

## Task 6: 检索集成衰减评分

**Files:**
- Modify: `backend/tars/memory/search.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — 衰减检索 + 命中强化**

追加到 `tests/test_memory_v3.py`:
```python
class TestDecaySearch:
    @pytest.mark.asyncio
    async def test_search_reinforces_hits(self, tmp_path):
        from tars.database import Database
        from tars.memory.archival import ArchivalManager
        from tars.memory.search import HybridSearch
        db = Database(db_path=str(tmp_path / "t.db"))
        am = ArchivalManager(db, embedding_provider=None)
        m = await am.insert(content="用户使用 Mac M1 笔记本", category="fact", importance=0.5, source="conversation")
        search = HybridSearch(db, embedding_provider=None)
        results = search.search("Mac M1", limit=5)
        assert any(r.id == m.id for r in results)
        # 命中后 access_count 应 >= 1
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT access_count FROM memories WHERE id = ?", (m.id,))
        assert cur.fetchone()[0] >= 1
```

- [ ] **Step 2: 运行测试，确认失败或行为异常**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestDecaySearch -v
```
预期：FAIL（没有强化逻辑）

- [ ] **Step 3: 改造 search.py，集成 decay 评分 + 强化**

完整重写 `backend/tars/memory/search.py`:
```python
"""混合搜索 — 语义 + FTS 关键词 + Ebbinghaus 衰减 + 命中强化"""
from typing import List, Tuple

from .deduplicator import cosine_similarity
from .embeddings import EmbeddingProvider, deserialize_vector
from .decay import decay_score, hours_since


class HybridSearch:
    """语义搜索 + FTS 关键词搜索 + 衰减加权"""

    def __init__(self, db, embedding_provider: EmbeddingProvider = None):
        self.db = db
        self.embedding_provider = embedding_provider

    def search(self, query: str, limit: int = 5) -> list:
        """混合搜索 + 衰减加权 + 命中强化"""
        scored: dict = {}  # mem_id -> (mem, score)

        # 1. 语义搜索（如有 embedding）
        if self.embedding_provider:
            try:
                self._semantic_score(query, scored)
            except Exception as e:
                print(f"[HybridSearch] 语义搜索失败: {e}")

        # 2. FTS 关键词搜索作为补充
        try:
            self._keyword_score(query, scored)
        except Exception:
            pass

        # 3. 排序取 top
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)[:limit]
        results = [mem for mem, _ in ranked]

        # 4. 命中强化
        for mem in results:
            try:
                self.db.reinforce_memory(mem.id)
            except Exception:
                pass

        return results

    def _semantic_score(self, query: str, scored: dict):
        query_vec = self.embedding_provider.encode([query])[0]
        all_memories = self.db.get_all_memories_with_metadata()
        for mem, embedding_blob, last_accessed_iso, importance, _source in all_memories:
            if not embedding_blob:
                continue
            mem_vec = deserialize_vector(embedding_blob)
            if not mem_vec:
                continue
            sim = cosine_similarity(query_vec, mem_vec)
            age_h = hours_since(last_accessed_iso)
            score = decay_score(sim, importance, age_h)
            scored[mem.id] = (mem, score)

    def _keyword_score(self, query: str, scored: dict):
        keyword_results = self.db.search_memories(query, limit=10)
        for mem in keyword_results:
            if mem.id in scored:
                continue
            # 关键词命中给固定基础分，再叠加衰减/重要性
            importance = getattr(mem, "importance", 0.5) or 0.5
            score = decay_score(0.5, importance, 0)  # 假设 last_accessed=now
            scored[mem.id] = (mem, score)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestDecaySearch -v
```
预期：PASS

- [ ] **Step 5: 跑现有 search 相关测试不回归**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v2.py -v 2>&1 | tail -20
```
预期：现有测试仍 PASS（如有失败需调整 search.py 兼容老接口）

- [ ] **Step 6: 提交**

```bash
cd backend && echo "Task 6 done — HybridSearch 衰减集成完成"
```

---

## Task 7: Reflector — 后处理反思 LLM

**Files:**
- Create: `backend/tars/memory/reflector.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — 解析 LLM 输出 + 应用 ops**

追加到 `tests/test_memory_v3.py`:
```python
class TestReflector:
    @pytest.mark.asyncio
    async def test_parse_ops_from_response(self):
        from tars.memory.reflector import Reflector
        text = '[{"op": "update_core", "block": "user_profile", "action": "append", "old": "", "new": "用户偏好 Go"}, {"op": "archive", "content": "项目用 Python 3.14", "category": "fact", "importance": 0.7, "source": "conversation"}]'
        ops = Reflector._parse_ops(text)
        assert len(ops) == 2
        assert ops[0]["op"] == "update_core"
        assert ops[1]["op"] == "archive"

    @pytest.mark.asyncio
    async def test_parse_handles_code_block(self):
        from tars.memory.reflector import Reflector
        text = '```json\n[{"op": "noop"}]\n```'
        ops = Reflector._parse_ops(text)
        assert ops == [{"op": "noop"}]

    @pytest.mark.asyncio
    async def test_parse_handles_garbage(self):
        from tars.memory.reflector import Reflector
        ops = Reflector._parse_ops("not json at all")
        assert ops == []

    @pytest.mark.asyncio
    async def test_apply_update_core(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        from tars.memory.archival import ArchivalManager
        from tars.memory.reflector import Reflector
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        am = ArchivalManager(db)
        reflector = Reflector(provider=None, core=cm, archival=am)
        cm.set("user_profile", "")
        await reflector._apply_op({"op": "update_core", "block": "user_profile", "action": "append", "new": "用户偏好 Go"})
        assert "Go" in cm.get("user_profile")

    @pytest.mark.asyncio
    async def test_apply_archive(self, tmp_path):
        from tars.database import Database
        from tars.memory.core_memory import CoreMemoryManager
        from tars.memory.archival import ArchivalManager
        from tars.memory.reflector import Reflector
        db = Database(db_path=str(tmp_path / "t.db"))
        cm = CoreMemoryManager(db)
        am = ArchivalManager(db)
        reflector = Reflector(provider=None, core=cm, archival=am)
        await reflector._apply_op({"op": "archive", "content": "用户使用 Mac M1", "category": "fact", "importance": 0.7, "source": "conversation"})
        recents = db.get_recent_memories(5)
        assert any("Mac M1" in m.content for m in recents)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestReflector -v
```
预期：FAIL（reflector 不存在）

- [ ] **Step 3: 实现 Reflector**

创建 `backend/tars/memory/reflector.py`:
```python
"""后处理反思 LLM — 每轮对话后异步更新 core memory + archive 长期记忆"""
import json
import re
from typing import List, Dict, Any, Optional

from .core_memory import CoreMemoryManager, BLOCK_NAMES
from .archival import ArchivalManager


REFLECTION_PROMPT = """你是记忆管理助手。基于本轮对话，判断需要做的记忆操作。

当前 core memory：
- persona: {persona}
- user_profile: {user_profile}
- project_context: {project_context}
- working_principles: {working_principles}

本轮对话（注意：本轮{web_marker}使用了 web 搜索）：
User: {user_msg}
Assistant: {assistant_msg}

输出严格的 JSON 数组，每个元素是一个操作。不要任何额外文字。

操作类型：
- {{"op": "update_core", "block": "<persona|user_profile|project_context|working_principles>", "action": "append|replace", "old": "<被替换的旧文本>", "new": "<新文本>"}}
- {{"op": "archive", "content": "<简洁事实>", "category": "<fact|preference|decision|domain_knowledge>", "importance": <0.0-1.0>, "source": "<conversation|web>"}}
- {{"op": "noop"}}

规则：
- 用户明确反馈的协作准则 → working_principles
- 用户身份/技术栈/偏好 → user_profile
- 项目目标/进展变化 → project_context
- 风格反馈 → persona
- 一次性事实/对话片段 → archive
- 若使用了 web 搜索且学到领域知识 → archive 时 source="web"，category="domain_knowledge"
- 无明显新信息 → 输出 [{{"op": "noop"}}]

只输出 JSON 数组。"""


class Reflector:
    """反思器：每轮对话后异步触发，更新 core + archival"""

    def __init__(
        self,
        provider,
        core: CoreMemoryManager,
        archival: ArchivalManager,
    ):
        self.provider = provider
        self.core = core
        self.archival = archival

    async def reflect(
        self,
        user_msg: str,
        assistant_msg: str,
        used_web: bool = False,
    ) -> List[Dict[str, Any]]:
        """异步反思入口；返回执行的 ops 列表（用于日志）"""
        if not self.provider:
            return []
        if not user_msg.strip() or not assistant_msg.strip():
            return []

        snapshot = self.core.get_all()
        prompt = REFLECTION_PROMPT.format(
            persona=snapshot.get("persona", "")[:300],
            user_profile=snapshot.get("user_profile", "")[:300],
            project_context=snapshot.get("project_context", "")[:300],
            working_principles=snapshot.get("working_principles", "")[:300],
            user_msg=user_msg[:1500],
            assistant_msg=assistant_msg[:1500],
            web_marker="" if used_web else "未",
        )

        try:
            from ..models import ChatMessage
            messages = [
                ChatMessage(role="system", content="你是记忆管理助手。只输出 JSON。"),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self.provider.chat(messages, stream=False, temperature=0.1)
            text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            print(f"[Reflector] LLM 调用失败: {e}")
            return []

        ops = self._parse_ops(text)
        applied = []
        for op in ops:
            try:
                if await self._apply_op(op):
                    applied.append(op)
            except Exception as e:
                print(f"[Reflector] op 应用失败 {op}: {e}")
        return applied

    @staticmethod
    def _parse_ops(text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        # 直接尝试
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass
        # ```json ... ```
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass
        # 找第一个 [...] 块
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                pass
        return []

    async def _apply_op(self, op: Dict[str, Any]) -> bool:
        kind = op.get("op")
        if kind == "noop":
            return False
        if kind == "update_core":
            block = op.get("block", "")
            if block not in BLOCK_NAMES:
                return False
            action = op.get("action", "append")
            new = op.get("new", "").strip()
            if not new:
                return False
            if action == "replace":
                old = op.get("old", "")
                return self.core.replace(block, old, new)
            return self.core.append(block, new)
        if kind == "archive":
            content = op.get("content", "").strip()
            if not content:
                return False
            category = op.get("category", "fact")
            importance = float(op.get("importance", 0.5))
            source = op.get("source", "conversation")
            mem = await self.archival.insert(
                content=content,
                category=category,
                importance=importance,
                source=source,
            )
            return mem is not None
        return False
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestReflector -v
```
预期：PASS（5/5）

- [ ] **Step 5: 提交**

```bash
cd backend && echo "Task 7 done — Reflector 实现完成"
```

---

## Task 8: 重写 MemoryManager 整合所有组件

**Files:**
- Modify: `backend/tars/memory/manager.py`
- Modify: `backend/tars/memory/__init__.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: 写测试 — 端到端集成**

追加到 `tests/test_memory_v3.py`:
```python
class TestMemoryManagerV3:
    def test_get_context_includes_core(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=None)
        mgr.core.set("user_profile", "用户偏好 Go")
        ctx = mgr.get_context_for_query("项目用什么语言")
        assert "用户偏好 Go" in ctx
        assert "## 核心记忆" in ctx

    def test_register_tools_returns_list(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=None)
        tools = mgr.get_tools()
        names = {t.name for t in tools}
        assert "core_memory_append" in names
        assert "core_memory_replace" in names
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestMemoryManagerV3 -v
```
预期：FAIL（manager 还是旧实现）

- [ ] **Step 3: 重写 MemoryManager**

完整覆盖 `backend/tars/memory/manager.py`:
```python
"""记忆管理器 V3 — 整合 Core + Archival + Reflector"""
from typing import Optional, List

from .core_memory import CoreMemoryManager, CoreMemoryAppendTool, CoreMemoryReplaceTool
from .archival import ArchivalManager
from .reflector import Reflector
from .search import HybridSearch
from .embeddings import EmbeddingProvider


class MemoryManager:
    """V3 记忆管理器：core memory + archival memory + reflector"""

    def __init__(
        self,
        db,
        provider=None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.db = db
        self.provider = provider
        self.embedding_provider = embedding_provider

        self.core = CoreMemoryManager(db)
        self.archival = ArchivalManager(db, embedding_provider)
        self.search = HybridSearch(db, embedding_provider)
        self.reflector = Reflector(provider, self.core, self.archival)

    def set_provider(self, provider):
        self.provider = provider
        self.reflector.provider = provider

    def get_context_for_query(self, query: str, limit: int = 5) -> str:
        """构建注入 system prompt 的记忆上下文：core memory + 检索到的 archival"""
        parts = []

        # Core memory（始终注入）
        core_render = self.core.render_for_prompt()
        if core_render.strip():
            parts.append(core_render)

        # Archival memory（语义+关键词检索）
        memories = self.search.search(query, limit)
        if memories:
            parts.append("\n## 相关长期记忆")
            for mem in memories:
                parts.append(f"- [{mem.category}] {mem.content}")

        return "\n".join(parts)

    async def reflect(self, user_msg: str, assistant_msg: str, used_web: bool = False):
        """每轮对话后由 Agent 异步调用"""
        return await self.reflector.reflect(user_msg, assistant_msg, used_web)

    async def add_manual_memory(self, content: str, category: str = "fact"):
        """手动添加（用于 API / 前端）"""
        return await self.archival.insert(content, category, importance=0.6, source="manual")

    def search_memories(self, query: str, limit: int = 5):
        return self.search.search(query, limit)

    def get_tools(self) -> List:
        """返回需要注册到 ToolRegistry 的工具列表"""
        return [
            CoreMemoryAppendTool(self.core),
            CoreMemoryReplaceTool(self.core),
        ]

    # 兼容老接口（main.py / agent.py 可能还在用）
    async def extract_and_save(self, conversation: str):
        """兼容老 API：旧的提取式接口现在是反思器的简化路径。
        conversation 格式："User: ...\\nAssistant: ..." """
        if "\n" in conversation:
            user_part, _, assistant_part = conversation.partition("\n")
        else:
            user_part, assistant_part = conversation, ""
        user_msg = user_part.replace("User:", "").strip()
        assistant_msg = assistant_part.replace("Assistant:", "").strip()
        return await self.reflect(user_msg, assistant_msg)
```

- [ ] **Step 4: 更新 `__init__.py` 导出**

完整覆盖 `backend/tars/memory/__init__.py`:
```python
from .manager import MemoryManager
from .core_memory import (
    CoreMemoryManager,
    CoreMemoryAppendTool,
    CoreMemoryReplaceTool,
    BLOCK_NAMES,
)
from .archival import ArchivalManager
from .reflector import Reflector
from .search import HybridSearch
from .decay import decay_score, hours_since
from .embeddings import EmbeddingProvider, LocalEmbeddingProvider
from .extractor import LLMMemoryExtractor, RegexExtractor
from .deduplicator import MemoryDeduplicator

__all__ = [
    "MemoryManager",
    "CoreMemoryManager", "CoreMemoryAppendTool", "CoreMemoryReplaceTool", "BLOCK_NAMES",
    "ArchivalManager", "Reflector",
    "HybridSearch", "decay_score", "hours_since",
    "EmbeddingProvider", "LocalEmbeddingProvider",
    "LLMMemoryExtractor", "RegexExtractor", "MemoryDeduplicator",
]
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestMemoryManagerV3 -v
```
预期：PASS

- [ ] **Step 6: 跑全部记忆测试不回归**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py tests/test_memory_v2.py -v 2>&1 | tail -30
```
预期：v3 全 PASS；v2 中 `extract_and_save` 等老接口测试仍 PASS

- [ ] **Step 7: 提交**

```bash
cd backend && echo "Task 8 done — MemoryManager V3 整合完成"
```

---

## Task 9: 接入 Agent 主流程

**Files:**
- Modify: `backend/tars/main.py`
- Modify: `backend/tars/agent/agent.py`
- Test: `backend/tests/test_memory_v3.py`

- [ ] **Step 1: main.py 注册 core memory 工具**

在 `backend/tars/main.py:118` 附近（创建 memory_manager 之后、tool_registry 注册区），加入：
```python
# 注册 core memory 编辑工具
for tool in memory_manager.get_tools():
    tool_registry.register(tool)
```

放置位置：找到 `tool_registry.register(...)` 的连续调用块，把上面这个 for 循环加在最后一个 register 后。

- [ ] **Step 2: agent.py 改用 used_web 标记的 reflect**

修改 `backend/tars/agent/agent.py`，定位到 `extract_and_save` 调用处（约 196 行）：

```python
# 10. 提取记忆（V3 反思器）
used_web = False
# ToolDispatcher 内部不会暴露使用了哪些工具，简化处理：
# 检查响应文本中是否包含 web 工具结果标记，或加一个 dispatcher 输出
# 这里简化：先全部按 used_web=False 处理，后续可优化。
try:
    applied = await self.memory_manager.reflect(user_content, full_response, used_web=used_web)
except Exception as e:
    print(f"[Agent] 反思失败: {e}")
    applied = []
if applied:
    await channel.send(session_id, {
        "type": "memory_extracted",
        "session_id": session_id,
        "memories": [{"op": op.get("op"), "summary": str(op)[:80]} for op in applied],
        "timestamp": now_iso(),
    })
```

替换原 `extract_and_save` 调用块。

- [ ] **Step 3: 加 web 使用追踪**

修改 `backend/tars/agent/agent.py` 中 `on_tool_call` 回调：
```python
used_web_flag = {"value": False}

async def on_tool_call(tool_name: str, arguments: Dict):
    if tool_name == "web":
        used_web_flag["value"] = True
    await channel.send(session_id, {
        "type": "tool_calling",
        "session_id": session_id,
        "tool": tool_name,
        "parameters": arguments,
        "timestamp": now_iso(),
    })
```

并在反思调用时使用 `used_web=used_web_flag["value"]`。

- [ ] **Step 4: 写集成测试 — agent 调用后 core memory 被更新**

追加到 `tests/test_memory_v3.py`:
```python
class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_reflect_updates_core_via_mock_provider(self, tmp_path):
        """模拟 LLM 返回 update_core op，验证 core memory 被更新"""
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        from tars.models.base import ModelResponse

        class MockProvider:
            async def chat(self, messages, stream=False, temperature=0.7, **kwargs):
                resp = ModelResponse(
                    content='[{"op":"update_core","block":"user_profile","action":"append","old":"","new":"用户偏好 Go 后端"}]',
                    model="mock",
                    usage={},
                )
                return resp

        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=MockProvider())
        mgr.core.set("user_profile", "")
        await mgr.reflect("我喜欢用 Go 写后端", "好的，我记住了")
        assert "Go 后端" in mgr.core.get("user_profile")

    @pytest.mark.asyncio
    async def test_reflect_archives_web_knowledge(self, tmp_path):
        from tars.database import Database
        from tars.memory.manager import MemoryManager
        from tars.models.base import ModelResponse

        class MockProvider:
            async def chat(self, messages, stream=False, temperature=0.7, **kwargs):
                return ModelResponse(
                    content='[{"op":"archive","content":"FastAPI 用 Pydantic v2 验证","category":"domain_knowledge","importance":0.7,"source":"web"}]',
                    model="mock",
                    usage={},
                )

        db = Database(db_path=str(tmp_path / "t.db"))
        mgr = MemoryManager(db, provider=MockProvider())
        await mgr.reflect("FastAPI 怎么验证参数", "用 Pydantic v2", used_web=True)
        recents = db.get_recent_memories(5)
        assert any("Pydantic" in m.content for m in recents)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_memory_v3.py::TestAgentIntegration -v
```
预期：PASS（2/2）

- [ ] **Step 6: 整体回归测试**

```bash
cd backend && ./venv/bin/python -m pytest tests/ -v 2>&1 | tail -40
```
预期：全部 PASS（含 test_memory_v3.py 全部用例 + 现有所有测试）

- [ ] **Step 7: 启动后端冒烟测试**

```bash
cd backend && ./venv/bin/python -c "
from tars.database import Database
from tars.memory import MemoryManager
db = Database(':memory:')
mgr = MemoryManager(db, provider=None)
mgr.core.set('user_profile', '用户使用 Mac M1')
ctx = mgr.get_context_for_query('我的环境')
print(ctx)
print('TOOLS:', [t.name for t in mgr.get_tools()])
"
```
预期：输出包含 "## 核心记忆"、"用户使用 Mac M1"，TOOLS 列表含 `core_memory_append` `core_memory_replace`

- [ ] **Step 8: 提交**

```bash
cd backend && echo "Task 9 done — V3 接入 Agent 主流程"
```

---

## Task 10: 文档更新

**Files:**
- Modify: `README.md`
- Modify: `docs/02-技术方案/` 下相关文档（如有专门的记忆文档）

- [ ] **Step 1: 检查现有记忆相关文档**

```bash
ls /Users/daobanxiang/myproject/TARS/docs/02-技术方案/ 2>&1
grep -rln "记忆\|memory" /Users/daobanxiang/myproject/TARS/docs/ 2>&1 | head -10
```

- [ ] **Step 2: 更新 README — 替换"记忆系统 V2"段落为 V3**

定位 README 中"记忆系统 V2"或"## 记忆系统"段落，替换为：
```markdown
## 记忆系统 V3（Letta 混合模式）

TARS 采用三层记忆架构：

1. **Core Memory（4 块固定区块）** — 注入 system prompt：
   - `persona` Agent 人格定位
   - `user_profile` 用户画像（身份/技术栈/偏好）
   - `project_context` 当前项目上下文
   - `working_principles` 协作准则累积
2. **Archival Memory（长期记忆）** — embedding 检索 + Ebbinghaus 衰减
3. **Reflector（反思器）** — 每轮对话后异步更新 core + archival

Agent 通过 `core_memory_append` / `core_memory_replace` 工具自主编辑核心记忆；反思器作为兜底每轮触发。
Web 工具搜索结果通过反思器自动沉淀为 `source=web` 的 archival 记忆。

详见 [docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md](docs/superpowers/specs/2026-05-06-memory-v3-letta-design.md)
```

- [ ] **Step 3: 提交**

```bash
echo "Task 10 done — 文档更新完成"
```

---

## 自检 Checklist

完成后逐条验证（Spec 对应关系）：

- ✅ Task 1 → Spec 5（数据库迁移）
- ✅ Task 2-3 → Spec 3.1, 3.3（4 块 core memory + 工具）
- ✅ Task 4-5 → Spec 3.2, 3.5, 3.6（archival + 衰减 + 强化）
- ✅ Task 6 → Spec 4.3（检索流程）
- ✅ Task 7 → Spec 3.4（反思器）
- ✅ Task 8 → Spec 5（文件结构整合）
- ✅ Task 9 → Spec 4.1, 4.2（主流程接入 + Web 沉淀标记）
- ✅ Task 10 → 文档同步

成功标准（Spec §9）验证手段：
1. 连续 3 次反馈"用 X 风格" → 手动 3 轮对话后查看 `core_memory_blocks.working_principles` 内容
2. 告诉一次"我用 Mac M1" → 后续提问环境时检查 system prompt 中 user_profile 是否含 M1
3. Web 工具学到事实后 → 第二次提问时观察是否还调用 web（需后端日志）
4. 100 条记忆下 top 5 相关性目测优于旧实现 → 准备 100 条样本数据手动评估
5. 24 小时无异常增长 → 启动后端 24 小时观察 sqlite 文件大小
