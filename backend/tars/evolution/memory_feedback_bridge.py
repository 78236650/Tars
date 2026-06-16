"""MemoryFeedbackBridge — Evolution → Memory 写入桥梁。

v5.0.5/A3+: 将 Evolution 分析结果（avoidance_rules / recommendations）
写回 Memory 系统，形成闭环。
"""
from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database.base import Database


class MemoryFeedbackBridge:
    """Evolution 分析结果 → Memory 写入。

    接收 MemoryAwareAnalyzer 产出的 patterns，将其转换为
    core memory 更新和 pinned 记忆，让后续对话能自动受益。
    """

    def __init__(self, db: "Database"):
        self.db = db

    def apply_patterns(self, patterns, tenant_id: str) -> Dict[str, int]:
        """将 MemoryPatterns 应用到 Memory 系统。"""
        stats = {"avoidance_rules": 0, "recommendations": 0}

        for rule in patterns.avoidance_rules:
            if self._apply_avoidance_rule(rule, tenant_id):
                stats["avoidance_rules"] += 1

        for rec in patterns.recommendations:
            if self._apply_recommendation(rec, tenant_id):
                stats["recommendations"] += 1

        return stats

    def _apply_avoidance_rule(self, rule: Dict[str, Any], tenant_id: str) -> bool:
        """将避免规则写入 working_principles。"""
        try:
            principle = f"⚠️ 避免：{rule['rule']}"
            self._append_core_block("working_principles", principle, tenant_id)
            return True
        except Exception:
            return False

    def _apply_recommendation(self, rec: Dict[str, Any], tenant_id: str) -> bool:
        """将高频方案推荐固定为 pinned memory。"""
        try:
            # 将 entity 相关的 solution 记忆 pin 住
            for mem_id in rec.get("source_memory_ids", []):
                try:
                    self.db.set_memory_pin(mem_id, pinned=True, tenant_id=tenant_id)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _append_core_block(self, block: str, content: str, tenant_id: str) -> bool:
        """追加一行到 core memory 区块（带去重）。"""
        try:
            from tars.memory.core_memory import CoreMemoryManager
            cm = CoreMemoryManager(self.db, tenant_id=tenant_id)
            return cm.append(block, content)
        except Exception:
            return False

    def publish_lesson_learned(self, tenant_id: str, correction_summary: str) -> Optional[str]:
        """将反复纠正总结为一篇 lesson_learned 记忆。"""
        try:
            import datetime
            from datetime import timezone, timedelta
            import uuid

            now = datetime.datetime.now(timezone(timedelta(hours=8)))
            mid = str(uuid.uuid4())
            conn = self.db._get_conn()
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO memories(id,tenant_id,content,category,importance,created_at,
                    updated_at,last_accessed,access_count,source,memory_type,pinned)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (mid, tenant_id, f"教训：{correction_summary}", "lesson_learned",
                 0.9, now, now, None, 0, "evolution", "procedural", 1),
            )
            try:
                cur.execute(
                    "INSERT INTO memories_fts(rowid,content,category) VALUES(last_insert_rowid(),?,?)",
                    (f"教训：{correction_summary}", "lesson_learned"),
                )
            except Exception:
                pass
            conn.commit()
            return mid
        except Exception:
            return None
