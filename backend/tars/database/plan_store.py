"""Plan + checkpoint persistence — v4.3.2"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base import Database
from ..orchestration.models import PlanCheckpoint, PlanStatus, TaskPlan

_plan_store_singleton: Optional["PlanStore"] = None


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def init_plan_store(db: Database) -> "PlanStore":
    global _plan_store_singleton
    store = PlanStore(db)
    store.ensure_schema()
    _plan_store_singleton = store
    return store


def get_plan_store() -> "PlanStore":
    global _plan_store_singleton
    if _plan_store_singleton is None:
        _plan_store_singleton = init_plan_store(Database())
    return _plan_store_singleton


class PlanStore:
    def __init__(self, db: Database):
        self.db = db

    def ensure_schema(self) -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                goal TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                workspace_path TEXT,
                pdca_ref TEXT,
                skill_id TEXT,
                estimated_duration_sec INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plan_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL REFERENCES task_plans(id),
                step_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                output TEXT,
                timestamp TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_checkpoints_plan ON plan_checkpoints(plan_id)"
        )
        conn.commit()

    def create(self, plan: TaskPlan) -> TaskPlan:
        if not plan.id:
            plan.id = str(uuid.uuid4())
        now = _now_iso()
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO task_plans
               (id, session_id, tenant_id, goal, steps_json, status, workspace_path,
                pdca_ref, skill_id, estimated_duration_sec, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                plan.id,
                plan.session_id,
                plan.tenant_id,
                plan.goal,
                json.dumps(plan.to_dict()["steps"], ensure_ascii=False),
                plan.status.value,
                plan.workspace_path,
                plan.pdca_ref,
                plan.skill_id,
                plan.estimated_duration_sec or len(plan.steps) * 30,
                now,
                now,
            ),
        )
        conn.commit()
        return plan

    def update_status(self, plan_id: str, status: PlanStatus) -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE task_plans SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, _now_iso(), plan_id),
        )
        conn.commit()

    def update_steps(self, plan_id: str, steps: List[Dict[str, Any]]) -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE task_plans SET steps_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(steps, ensure_ascii=False), _now_iso(), plan_id),
        )
        conn.commit()

    def get(self, plan_id: str) -> Optional[TaskPlan]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, session_id, tenant_id, goal, steps_json, status, workspace_path,
                      pdca_ref, skill_id, estimated_duration_sec
               FROM task_plans WHERE id = ?""",
            (plan_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        steps = json.loads(row[4] or "[]")
        return TaskPlan.from_dict({
            "id": row[0],
            "session_id": row[1],
            "tenant_id": row[2],
            "goal": row[3],
            "steps": steps,
            "status": row[5],
            "workspace_path": row[6] or ".",
            "pdca_ref": row[7],
            "skill_id": row[8],
            "estimated_duration_sec": row[9] or 0,
        })

    def list_by_tenant(self, tenant_id: str, limit: int = 50) -> List[TaskPlan]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id FROM task_plans WHERE tenant_id = ?
               ORDER BY updated_at DESC LIMIT ?""",
            (tenant_id, limit),
        )
        return [self.get(r[0]) for r in cur.fetchall() if self.get(r[0])]

    def add_checkpoint(self, checkpoint: PlanCheckpoint) -> None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO plan_checkpoints
               (plan_id, step_id, status, output, timestamp, retry_count)
               VALUES (?,?,?,?,?,?)""",
            (
                checkpoint.plan_id,
                checkpoint.step_id,
                checkpoint.status,
                (checkpoint.output or "")[:2000],
                checkpoint.timestamp or _now_iso(),
                checkpoint.retry_count,
            ),
        )
        conn.commit()

    def get_checkpoints(self, plan_id: str) -> List[PlanCheckpoint]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT plan_id, step_id, status, output, timestamp, retry_count
               FROM plan_checkpoints WHERE plan_id = ? ORDER BY step_id, id""",
            (plan_id,),
        )
        return [
            PlanCheckpoint(
                plan_id=r[0],
                step_id=r[1],
                status=r[2],
                output=r[3],
                timestamp=r[4],
                retry_count=r[5] or 0,
            )
            for r in cur.fetchall()
        ]

    def get_last_done_step(self, plan_id: str) -> int:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT MAX(step_id) FROM plan_checkpoints
               WHERE plan_id = ? AND status = 'done'""",
            (plan_id,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def get_detail(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = self.get(plan_id)
        if not plan:
            return None
        data = plan.to_dict()
        data["checkpoints"] = [c.to_dict() for c in self.get_checkpoints(plan_id)]
        return data
