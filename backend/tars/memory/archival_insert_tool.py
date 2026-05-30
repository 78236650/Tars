"""v2.2 紧急写入通道 — archival_insert 工具"""
import json
from typing import Any, Dict

from tars.tools.base import BaseTool, ToolResult


class ArchivalInsertTool(BaseTool):
    name: str = "archival_insert"
    description: str = (
        "同步写入一条长期记忆（Episodic）。仅在用户明确要求记住某条信息时调用。"
        "如\"记住我是左撇子\"、\"这条要记住\"。自动反思器已覆盖一般信息，不要为普通陈述调用此工具。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要记住的事实（一句话）"},
            "category": {"type": "string", "description": "分类", "enum": ["fact", "preference", "decision", "domain_knowledge"]},
            "importance": {"type": "number", "description": "重要性 0-1", "default": 0.9},
            "entity_refs": {"type": "string", "description": "关联实体 JSON 数组，如 [{\"name\":\"TARS\",\"type\":\"project\"}]"},
        },
        "required": ["content", "category"],
    }

    def __init__(self, db):
        self.db = db

    async def execute(self, **kwargs) -> ToolResult:
        content = kwargs.get("content", "").strip()
        category = kwargs.get("category", "fact")
        importance = float(kwargs.get("importance", 0.9))
        entity_refs_raw = kwargs.get("entity_refs", "")

        if not content or len(content) < 3:
            return ToolResult(success=False, output="", error="内容太短")

        entity_refs = None
        if entity_refs_raw:
            try:
                entity_refs = json.loads(entity_refs_raw) if isinstance(entity_refs_raw, str) else entity_refs_raw
            except json.JSONDecodeError:
                pass

        import uuid
        from datetime import datetime, timezone, timedelta
        from tars.context import get_current_user_id
        from tars.org import ORG_ID

        now = datetime.now(timezone(timedelta(hours=8)))
        mid = str(uuid.uuid4())

        conn = self.db._get_conn()
        cur = conn.cursor()
        refs_json = json.dumps(entity_refs, ensure_ascii=False) if entity_refs else None
        try:
            writer_user_id = get_current_user_id()
        except RuntimeError:
            writer_user_id = None
        cur.execute(
            """
            INSERT INTO memories(id,tenant_id,user_id,content,category,importance,created_at,updated_at,access_count,source,event_time,entity_refs)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (mid, ORG_ID, writer_user_id, content, category, importance, now, now, 0, "urgent", now.isoformat(), refs_json),
        )
        try:
            cur.execute("INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)", (content, category))
        except Exception:
            pass
        conn.commit()
        return ToolResult(success=True, output=f"已记住: {content[:60]}")
