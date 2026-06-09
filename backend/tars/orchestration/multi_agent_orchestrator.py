"""总调度 Agent：派活给子 Agent，全程落编排记忆。"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from ..memory.manager import MemoryManager
from ..agent.subagent_manager import SubAgentManager
from .orchestration_memory import OrchestrationMemory
from .dag import validate_acyclic, CyclicDependencyError


def decompose_goal(goal: str) -> List[dict]:
    """MVP 规则拆解：港航关键词 → subtasks（yard 串行在 berth/vessel 之后）。"""
    g = goal.lower()
    subs: List[dict] = []
    if any(k in g for k in ["靠泊", "泊位", "berth", "靠"]):
        subs.append({
            "agent_type": "berth",
            "task": f"为目标选泊位: {goal}",
            "phase": "parallel",
        })
    if any(k in g for k in ["卸", "装", "堆", "箱", "yard", "堆场"]):
        subs.append({
            "agent_type": "yard",
            "task": f"分配堆场箱位: {goal}",
            "phase": "serial",
        })
    if any(k in g for k in ["船", "航次", "eta", "vessel", "cosco"]):
        subs.append({
            "agent_type": "vessel",
            "task": f"确认船舶动态: {goal}",
            "phase": "parallel",
        })
    if not subs:
        subs.append({"agent_type": "research", "task": goal, "phase": "parallel"})
    return subs


class MultiAgentOrchestrator:
    def __init__(self, db, tenant_id: str = "default", subagent_manager=None):
        self.db = db
        self.tenant_id = tenant_id
        self.mem = OrchestrationMemory(db=db, tenant_id=tenant_id)
        self.subagents = subagent_manager or SubAgentManager()

    def _decompose(self, goal: str) -> List[dict]:
        return decompose_goal(goal)

    @staticmethod
    def _validate_no_cycles(subtasks: List[dict]) -> None:
        """检测 subtasks 间 depends_on 循环(v5.0.5/A5)。

        节点 id 优先取显式 'id',否则用列表下标。无 depends_on 字段时图无边,
        天然无环 —— 仅当调用方提供依赖关系时才有意义。
        """
        deps: dict = {}
        # 先建立 下标/id → 规范 id 的映射
        id_of = {}
        for idx, st in enumerate(subtasks or []):
            nid = st.get("id", idx)
            id_of[idx] = nid
            id_of[nid] = nid
        for idx, st in enumerate(subtasks or []):
            nid = id_of[idx]
            raw_deps = st.get("depends_on") or []
            deps[nid] = [id_of.get(d, d) for d in raw_deps]
        if any(deps.get(n) for n in deps):
            validate_acyclic(deps)

    def _enrich_subtasks(self, subtasks: List[dict], domain_ctx: str) -> List[dict]:
        enriched = []
        for st in subtasks:
            item = dict(st)
            ctx = dict(item.get("context") or {})
            ctx["domain_memory"] = domain_ctx
            ctx["tenant_id"] = self.tenant_id
            item["context"] = ctx
            enriched.append(item)
        return enriched

    def _publish_shared_from_outputs(self, task_id: str, outputs: List[dict]) -> None:
        for row in outputs:
            agent = row.get("agent_type")
            text = str(row.get("output") or "")
            if agent == "berth" and text:
                self.mem.set_shared(task_id, "berth", {"recommendation": text}, by="berth")
            elif agent == "vessel" and text:
                self.mem.set_shared(task_id, "vessel", {"status": text}, by="vessel")
            elif agent == "yard" and text:
                self.mem.set_shared(task_id, "yard", {"allocation": text}, by="yard")

    def _check_berth_conflicts(self, task_id: str) -> List[str]:
        shared = self.mem.get_shared(task_id)
        berth = shared.get("berth") or {}
        rec = str(berth.get("recommendation", ""))
        match = re.search(r"(\d+)\s*号泊位", rec)
        if not match:
            match = re.search(r"(\d+)\s*号", rec)
        if not match:
            return []
        berth_no = match.group(1)
        rows = self.db.fetch_all(
            """
            SELECT c.task_id, c.value
            FROM agent_collaboration_ctx c
            JOIN agent_tasks t ON t.id = c.task_id
            WHERE c.key = 'berth' AND c.task_id != ? AND t.tenant_id = ?
              AND t.status IN ('running', 'done')
            ORDER BY t.created_at DESC
            LIMIT 20
            """,
            (task_id, self.tenant_id),
        )
        warnings: List[str] = []
        needle = f"{berth_no}号"
        for row in rows:
            try:
                payload = json.loads(row["value"])
                other = str(payload.get("recommendation", ""))
            except (json.JSONDecodeError, TypeError):
                other = str(row["value"])
            if needle in other:
                short_id = row["task_id"][:8]
                warnings.append(f"泊位 {berth_no} 号可能与任务 {short_id}… 存在窗口冲突")
        return warnings

    async def orchestrate(
        self,
        session_id: str,
        goal: str,
        subtasks: Optional[List[dict]] = None,
    ) -> dict:
        plan = subtasks if subtasks is not None else self._decompose(goal)
        # v5.0.5/A5: 编排前检测 DAG 循环依赖,有环则 fail-fast,避免死锁/空转。
        try:
            self._validate_no_cycles(plan)
        except CyclicDependencyError as e:
            return {"task_id": None, "status": "rejected", "error": str(e)}
        task_id = self.mem.start_task(session_id=session_id, goal=goal)
        try:
            try:
                domain_ctx = (
                    MemoryManager(db=self.db)
                    .for_tenant(self.tenant_id)
                    .get_context_for_query(goal)
                )
            except Exception:
                domain_ctx = ""

            enriched = self._enrich_subtasks(plan, domain_ctx)
            parallel = [t for t in enriched if t.get("phase", "parallel") != "serial"]
            serial = [t for t in enriched if t.get("phase") == "serial"]

            if parallel:
                await self.subagents.run_parallel_tasks(
                    parallel, orch_mem=self.mem, task_id=task_id
                )
                self._publish_shared_from_outputs(task_id, self.mem.get_outputs(task_id))

            if serial:
                await self.subagents.run_parallel_tasks(
                    serial, orch_mem=self.mem, task_id=task_id
                )
                self._publish_shared_from_outputs(task_id, self.mem.get_outputs(task_id))

            conflicts = self._check_berth_conflicts(task_id)
            status = "done"
            if conflicts:
                self.mem.set_shared(task_id, "conflicts", conflicts, by="orchestrator")
                status = "done"

            self.mem.finish_task(task_id, status=status)
            return {
                "task_id": task_id,
                "status": status,
                "subtasks": plan,
                "outputs": self.mem.get_outputs(task_id),
                "shared": self.mem.get_shared(task_id),
                "conflicts": conflicts,
            }
        except Exception as e:
            self.mem.finish_task(task_id, status="failed")
            return {"task_id": task_id, "status": "failed", "error": str(e)}
