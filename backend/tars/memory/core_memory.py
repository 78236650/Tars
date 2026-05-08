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

    def _is_duplicate_line(self, current: str, content: str) -> bool:
        """检查 content 是否与 current 中某一行几乎相同（去重）"""
        c = content.strip()
        if not c:
            return True
        # 精确匹配
        if c in current:
            return True
        # 按行比较，忽略首尾空格
        for line in current.split("\n"):
            if line.strip() == c:
                return True
            # 子串包含检测（新内容被某行完全包含）
            if len(c) > 10 and c in line:
                return True
            if len(line.strip()) > 10 and line.strip() in c:
                return True
        return False

    def _enforce_line_limit(self, content: str, max_lines: int = 30) -> str:
        """限制最大行数，删除最旧的行"""
        lines = content.split("\n")
        if len(lines) <= max_lines:
            return content
        # 保留最后 max_lines 行
        return "\n".join(lines[-max_lines:])

    def append(self, block: str, content: str) -> bool:
        content = content.strip()
        if not content:
            return False
        current = self.get(block)
        # 去重检查
        if self._is_duplicate_line(current, content):
            return False  # 静默跳过，不报错
        sep = "\n" if current and not current.endswith("\n") else ""
        new = current + sep + content
        new = self._enforce_line_limit(new)
        return self.set(block, new)

    def replace(self, block: str, old: str, new: str) -> bool:
        current = self.get(block)
        old = old.strip()
        new = new.strip()
        if not new:
            return False
        if old and old in current:
            updated = current.replace(old, new, 1)
        elif old:
            # old 不存在 → 当作追加（带去重）
            return self.append(block, new)
        else:
            # 无 old → 追加
            return self.append(block, new)
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
        # 先检查是否重复
        current = self.manager.get(block)
        if self.manager._is_duplicate_line(current, content):
            return ToolResult(success=True, output=f"(已存在，跳过) {block}: {content[:50]}")
        ok = self.manager.append(block, content)
        if ok:
            return ToolResult(success=True, output=f"已追加到 {block}: {content[:50]}")
        return ToolResult(success=False, output="", error="追加失败（可能达到上限）")


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
