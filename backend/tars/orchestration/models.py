"""任务编排数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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
class TaskPlan:
    goal: str
    steps: List[TaskStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        plan = cls(goal=data.get("goal", ""))
        for s in data.get("steps", []):
            step = TaskStep(
                id=s.get("id", 0),
                description=s.get("description", ""),
                tool=s.get("tool", ""),
                arguments=s.get("arguments", {}),
                depends_on=s.get("depends_on", []),
            )
            plan.steps.append(step)
        return plan
