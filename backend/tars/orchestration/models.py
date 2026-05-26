"""任务编排数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..config.plan_gate import PlanGateConfig, plan_gate_config


DANGEROUS_TOOLS = frozenset({"shell", "file_write", "network"})


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    id: int
    description: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    output: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "retries": self.retries,
        }


@dataclass
class PlanCheckpoint:
    plan_id: str
    step_id: int
    status: str
    output: Optional[str] = None
    timestamp: str = ""
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "status": self.status,
            "output": self.output,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
        }


@dataclass
class TaskPlan:
    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    id: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    session_id: str = "default"
    tenant_id: str = "default"
    workspace_path: str = "."
    pdca_ref: Optional[str] = None
    skill_id: Optional[str] = None
    estimated_duration_sec: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "workspace_path": self.workspace_path,
            "pdca_ref": self.pdca_ref,
            "skill_id": self.skill_id,
            "estimated_duration_sec": self.estimated_duration_sec or len(self.steps) * 30,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        status_raw = data.get("status", PlanStatus.DRAFT.value)
        try:
            status = PlanStatus(status_raw)
        except ValueError:
            status = PlanStatus.DRAFT

        plan = cls(
            goal=data.get("goal", ""),
            id=data.get("id", ""),
            status=status,
            session_id=data.get("session_id", "default"),
            tenant_id=data.get("tenant_id", "default"),
            workspace_path=data.get("workspace_path", "."),
            pdca_ref=data.get("pdca_ref"),
            skill_id=data.get("skill_id"),
            estimated_duration_sec=int(data.get("estimated_duration_sec") or 0),
        )
        for s in data.get("steps", []):
            step = TaskStep(
                id=s.get("id", 0),
                description=s.get("description", ""),
                tool=s.get("tool", ""),
                arguments=s.get("arguments", {}),
                depends_on=s.get("depends_on", []),
            )
            raw_status = s.get("status")
            if raw_status:
                try:
                    step.status = StepStatus(raw_status)
                except ValueError:
                    pass
            step.output = s.get("output")
            step.error = s.get("error")
            step.retries = int(s.get("retries") or 0)
            plan.steps.append(step)
        if not plan.estimated_duration_sec:
            plan.estimated_duration_sec = len(plan.steps) * 30
        return plan


def auto_approve_eligible(plan: TaskPlan, config: Optional[PlanGateConfig] = None) -> bool:
    """Return True when plan can skip user review."""
    cfg = config or plan_gate_config
    if not cfg.enabled:
        return True
    if cfg.force_auto_approve:
        return True
    if cfg.always_approve:
        return False

    step_count = len(plan.steps)
    tools = {s.tool for s in plan.steps}
    has_dangerous = bool(tools & DANGEROUS_TOOLS)

    if step_count >= 5:
        return False
    if step_count >= 3 and has_dangerous:
        return False
    if step_count < cfg.auto_approve_threshold and not has_dangerous:
        return True
    return False
