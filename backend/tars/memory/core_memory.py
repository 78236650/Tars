"""Core Memory — Letta 模式的 4 块固定区块管理"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict


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
