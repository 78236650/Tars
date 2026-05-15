"""Working Context 读写 — v2.2 会话级场景画像"""
import json
from typing import Optional


class WorkingContextManager:
    """管理 working_contexts 表的读写"""

    def __init__(self, db, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id

    def get(self, session_id: str) -> dict:
        return self.db.get_working_context(session_id, tenant_id=self.tenant_id) or {}

    def update(self, session_id: str, **kwargs):
        self.db.upsert_working_context(session_id, tenant_id=self.tenant_id, **kwargs)

    def set_scene_result(self, session_id: str, scene: dict):
        """将 Scene Analyzer 输出写入 Working Context"""
        entities = scene.get("entities_mentioned", [])
        focus_ids = []
        from tars.memory.entity_id import compute_entity_id
        for e in entities[-8:]:  # 最多 8 个，保留最新的
            eid = compute_entity_id(e.get("type", "concept"), e.get("name", ""))
            focus_ids.append(eid)

        self.update(
            session_id,
            focus_entities=focus_ids,
            current_intent=scene.get("intent", "unknown"),
            intent_confidence=scene.get("intent_confidence", 0),
            open_threads=scene.get("open_thread_refs", []),
            last_scene_snapshot=scene,
        )

    def cleanup_expired(self, max_age_hours: int = 72):
        self.db.cleanup_working_contexts(max_age_hours, tenant_id=self.tenant_id)
