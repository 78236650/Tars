"""Skills Curator — v4.0.0 Phase 4.

Tracks skill usage statistics and provides archive/activate lifecycle.
Archived skills are excluded from auto-activation by the skill router.
"""
import time
from typing import Optional


class SkillCurator:
    """Track skill usage and manage archive lifecycle."""

    def __init__(self, db):
        self._db = db
        self._ensure_table()

    def _ensure_table(self):
        try:
            conn = self._db._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_usage (
                    skill_id TEXT PRIMARY KEY,
                    total_calls INTEGER NOT NULL DEFAULT 0,
                    last_called REAL NOT NULL DEFAULT 0.0,
                    state TEXT NOT NULL DEFAULT 'active'
                )
            """)
            conn.commit()
        except Exception:
            pass

    def record_call(self, skill_id: str):
        """Increment call count for a skill."""
        try:
            now = time.time()
            conn = self._db._get_conn()
            conn.execute("""
                INSERT INTO skill_usage (skill_id, total_calls, last_called, state)
                VALUES (?, 1, ?, 'active')
                ON CONFLICT(skill_id) DO UPDATE SET
                    total_calls = total_calls + 1,
                    last_called = excluded.last_called
            """, (skill_id, now))
            conn.commit()
        except Exception:
            pass

    def archive(self, skill_id: str):
        """Archive a skill — sets state='archived'."""
        try:
            now = time.time()
            conn = self._db._get_conn()
            conn.execute("""
                INSERT INTO skill_usage (skill_id, total_calls, last_called, state)
                VALUES (?, 0, ?, 'archived')
                ON CONFLICT(skill_id) DO UPDATE SET state = 'archived'
            """, (skill_id, now))
            conn.commit()
        except Exception:
            pass

    def activate(self, skill_id: str):
        """Re-activate a previously archived skill."""
        try:
            conn = self._db._get_conn()
            conn.execute("""
                INSERT INTO skill_usage (skill_id, total_calls, last_called, state)
                VALUES (?, 0, ?, 'active')
                ON CONFLICT(skill_id) DO UPDATE SET state = 'active'
            """, (skill_id, time.time()))
            conn.commit()
        except Exception:
            pass

    def is_archived(self, skill_id: str) -> bool:
        """Return True if the skill is archived."""
        try:
            conn = self._db._get_conn()
            row = conn.execute(
                "SELECT state FROM skill_usage WHERE skill_id = ?",
                (skill_id,)
            ).fetchone()
            if row is not None:
                return row[0] == "archived"
        except Exception:
            pass
        return False

    def get_stats(self) -> list:
        """Get all skill usage stats sorted by call count descending."""
        try:
            conn = self._db._get_conn()
            rows = conn.execute(
                "SELECT skill_id, total_calls, last_called, state "
                "FROM skill_usage ORDER BY total_calls DESC"
            ).fetchall()
            return [
                {
                    "skill_id": r[0],
                    "total_calls": r[1],
                    "last_called": r[2],
                    "state": r[3],
                }
                for r in rows
            ]
        except Exception:
            return []

    def get_skill_stats(self, skill_id: str) -> Optional[dict]:
        """Get stats for a single skill."""
        try:
            conn = self._db._get_conn()
            row = conn.execute(
                "SELECT skill_id, total_calls, last_called, state "
                "FROM skill_usage WHERE skill_id = ?",
                (skill_id,)
            ).fetchone()
            if row:
                return {
                    "skill_id": row[0],
                    "total_calls": row[1],
                    "last_called": row[2],
                    "state": row[3],
                }
        except Exception:
            pass
        return None


# ── Global singleton ────────────────────────────────────────────────

skill_curator: Optional[SkillCurator] = None


def init_skill_curator(db) -> SkillCurator:
    global skill_curator
    skill_curator = SkillCurator(db)
    return skill_curator
