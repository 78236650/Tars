"""Skill router recommendation log — feeds Evolution SkillOptimizer."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base import Database

_store_singleton: Optional["SkillRoutingStore"] = None


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def init_skill_routing_store(db: Database) -> "SkillRoutingStore":
    global _store_singleton
    store = SkillRoutingStore(db)
    store.ensure_schema()
    _store_singleton = store
    return store


def get_skill_routing_store() -> Optional["SkillRoutingStore"]:
    return _store_singleton


class SkillRoutingStore:
    def __init__(self, db: Database):
        self.db = db

    def ensure_schema(self) -> None:
        conn = self.db._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_routing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0,
                match_reason TEXT,
                adopted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_skill_routing_skill ON skill_routing_events(skill_id)"
        )
        conn.commit()

    def record_recommendations(
        self,
        session_id: str,
        candidates: List[Any],
    ) -> None:
        if not candidates:
            return
        conn = self.db._get_conn()
        now = _now_iso()
        for candidate in candidates:
            skill_id = getattr(candidate, "skill_id", None) or candidate.get("skill_id")
            if not skill_id:
                continue
            score = float(getattr(candidate, "score", 0) or candidate.get("score", 0))
            reason = getattr(candidate, "match_reason", None) or candidate.get("match_reason")
            conn.execute(
                """
                INSERT INTO skill_routing_events
                    (session_id, skill_id, score, match_reason, adopted, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (session_id, skill_id, score, reason, now),
            )
        conn.commit()

    def mark_adopted(self, session_id: str, skill_id: str) -> None:
        conn = self.db._get_conn()
        row = conn.execute(
            """
            SELECT id FROM skill_routing_events
            WHERE session_id = ? AND skill_id = ? AND adopted = 0
            ORDER BY id DESC LIMIT 1
            """,
            (session_id, skill_id),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE skill_routing_events SET adopted = 1 WHERE id = ?",
                (row[0],),
            )
            conn.commit()
            return
        conn.execute(
            """
            INSERT INTO skill_routing_events
                (session_id, skill_id, score, match_reason, adopted, created_at)
            VALUES (?, ?, 1.0, 'direct_activation', 1, ?)
            """,
            (session_id, skill_id, _now_iso()),
        )
        conn.commit()

    def adoption_stats(self, min_recommendations: int = 10) -> List[Dict[str, Any]]:
        conn = self.db._get_conn()
        rows = conn.execute(
            """
            SELECT skill_id,
                   COUNT(*) AS recommendations,
                   SUM(adopted) AS adoptions
            FROM skill_routing_events
            GROUP BY skill_id
            HAVING COUNT(*) >= ?
            """,
            (min_recommendations,),
        ).fetchall()
        stats: List[Dict[str, Any]] = []
        for skill_id, recommendations, adoptions in rows:
            recs = int(recommendations or 0)
            adops = int(adoptions or 0)
            stats.append(
                {
                    "skill_id": skill_id,
                    "recommendations": recs,
                    "adoptions": adops,
                    "adoption_rate": round(adops / recs, 3) if recs else 0.0,
                }
            )
        return stats
