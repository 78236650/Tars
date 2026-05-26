"""Verification audit persistence — v4.3.2"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base import Database
from ..orchestration.verification import VerifyResult

_audit_store_singleton: Optional["VerificationAuditStore"] = None


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


@dataclass
class VerificationAuditRecord:
    id: int
    plan_id: str
    skill_id: Optional[str]
    passed: bool
    status: str
    results_json: str
    timestamp: str


def init_verification_audit_store(db: Database) -> "VerificationAuditStore":
    global _audit_store_singleton
    store = VerificationAuditStore(db)
    store.ensure_schema()
    _audit_store_singleton = store
    return store


def get_verification_audit_store() -> "VerificationAuditStore":
    global _audit_store_singleton
    if _audit_store_singleton is None:
        _audit_store_singleton = init_verification_audit_store(Database())
    return _audit_store_singleton


class VerificationAuditStore:
    def __init__(self, db: Database):
        self.db = db

    def ensure_schema(self) -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verification_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                skill_id TEXT,
                passed INTEGER NOT NULL,
                status TEXT NOT NULL,
                results_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_verification_audit_plan ON verification_audit(plan_id)"
        )
        conn.commit()

    def record(self, plan_id: str, skill_id: Optional[str], result: VerifyResult) -> int:
        conn = self.db._get_conn()
        cur = conn.cursor()
        payload = [
            {
                "command": s.command,
                "expect": s.expect,
                "passed": s.passed,
                "message": s.message,
                "exit_code": s.exit_code,
                "duration_ms": s.duration_ms,
            }
            for s in result.step_results
        ]
        cur.execute(
            """INSERT INTO verification_audit
               (plan_id, skill_id, passed, status, results_json, timestamp)
               VALUES (?,?,?,?,?,?)""",
            (
                plan_id,
                skill_id,
                1 if result.passed else 0,
                result.status,
                json.dumps(payload, ensure_ascii=False),
                _now_iso(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

    def list_by_plan(self, plan_id: str) -> List[Dict[str, Any]]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, plan_id, skill_id, passed, status, results_json, timestamp
               FROM verification_audit WHERE plan_id = ? ORDER BY id DESC""",
            (plan_id,),
        )
        rows = []
        for r in cur.fetchall():
            rows.append({
                "id": r[0],
                "plan_id": r[1],
                "skill_id": r[2],
                "passed": bool(r[3]),
                "status": r[4],
                "step_results": json.loads(r[5] or "[]"),
                "timestamp": r[6],
            })
        return rows

    def latest_for_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        items = self.list_by_plan(plan_id)
        return items[0] if items else None
