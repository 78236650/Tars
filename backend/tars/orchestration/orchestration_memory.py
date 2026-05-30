"""多 Agent 编排记忆：一次调度任务的产出与共享黑板落库。"""
import json
import uuid
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat()


class OrchestrationMemory:
    def __init__(self, db, tenant_id: str = "default"):
        self.db = db
        self.tenant_id = tenant_id

    def start_task(self, session_id: str, goal: str, orchestrator: str = "master") -> str:
        tid = str(uuid.uuid4())
        now = _now()
        self.db.execute(
            "INSERT INTO agent_tasks (id,tenant_id,session_id,goal,status,orchestrator,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (tid, self.tenant_id, session_id, goal, "running", orchestrator, now, now),
        )
        return tid

    def record_output(self, task_id: str, agent_type: str, subtask: str, output: str, status: str = "done"):
        self.db.execute(
            "INSERT INTO agent_task_outputs (id,task_id,agent_type,subtask,output,status,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), task_id, agent_type, subtask, output, status, _now()),
        )

    def get_outputs(self, task_id: str) -> list:
        return self.db.fetch_all(
            "SELECT agent_type,subtask,output,status FROM agent_task_outputs WHERE task_id=? ORDER BY created_at",
            (task_id,),
        )

    def set_shared(self, task_id: str, key: str, value, by: str):
        self.db.execute(
            "INSERT INTO agent_collaboration_ctx (task_id,key,value,updated_by,updated_at)"
            " VALUES (?,?,?,?,?) ON CONFLICT(task_id,key) DO UPDATE SET value=excluded.value,"
            " updated_by=excluded.updated_by, updated_at=excluded.updated_at",
            (task_id, key, json.dumps(value, ensure_ascii=False), by, _now()),
        )

    def get_shared(self, task_id: str) -> dict:
        rows = self.db.fetch_all(
            "SELECT key,value FROM agent_collaboration_ctx WHERE task_id=?", (task_id,)
        )
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def finish_task(self, task_id: str, status: str = "done"):
        self.db.execute(
            "UPDATE agent_tasks SET status=?, updated_at=? WHERE id=?",
            (status, _now(), task_id),
        )

    def get_task(self, task_id: str) -> dict:
        return self.db.fetch_one("SELECT * FROM agent_tasks WHERE id=?", (task_id,))

    def list_tasks(self, page: int = 1, page_size: int = 20) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        total_row = self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM agent_tasks WHERE tenant_id=?",
            (self.tenant_id,),
        )
        total = int(total_row["cnt"]) if total_row else 0
        tasks = self.db.fetch_all(
            "SELECT id,session_id,goal,status,orchestrator,created_at,updated_at"
            " FROM agent_tasks WHERE tenant_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (self.tenant_id, page_size, offset),
        )
        return {"tasks": tasks, "page": page, "page_size": page_size, "total": total}

    def get_task_detail(self, task_id: str) -> dict | None:
        task = self.get_task(task_id)
        if not task:
            return None
        return {
            "task": task,
            "outputs": self.get_outputs(task_id),
            "shared": self.get_shared(task_id),
        }
