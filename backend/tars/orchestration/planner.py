"""任务规划工具 — LLM 通过调用它提交执行计划"""
from typing import Any, Dict

from ..tools.base import BaseTool, ToolResult
from .models import TaskPlan


class TaskPlannerTool(BaseTool):
    name: str = "task_planner"
    description: str = (
        "为复杂多步骤任务制定执行计划。"
        "当用户请求涉及 3 步以上操作、创建项目脚手架、部署服务等复杂工作流时使用。"
        "简单请求（单次工具调用或对话）不要使用此工具。"
        "提交计划后系统会自动按步骤执行并反馈进度。"
    )
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "最终目标的简短描述"},
            "steps": {
                "type": "array",
                "description": "执行步骤列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "步骤 ID（从 1 递增）"},
                        "description": {"type": "string", "description": "步骤描述"},
                        "tool": {"type": "string", "description": "要调用的工具名，如 shell/file_write/network"},
                        "arguments": {
                            "type": "object",
                            "description": "工具参数。可用 {{step_N.output}} 引用前序步骤输出",
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "依赖的步骤 ID 列表",
                        },
                    },
                    "required": ["id", "description", "tool", "arguments"],
                },
            },
        },
        "required": ["goal", "steps"],
    }

    def __init__(self):
        self._pending_plan = None

    async def execute(self, **kwargs) -> ToolResult:
        """提交计划 — 不真正执行，只是传递给 TaskExecutor"""
        goal = kwargs.get("goal", "")
        steps = kwargs.get("steps", [])

        if not goal or not steps:
            return ToolResult(success=False, output="", error="计划需要 goal 和 steps")

        plan = TaskPlan.from_dict({"goal": goal, "steps": steps})
        self._pending_plan = plan

        return ToolResult(
            success=True,
            output=f"计划已提交: {goal}（{len(plan.steps)} 步）。系统将按计划执行。",
            metadata={"plan": plan.to_dict(), "is_plan": True},
        )

    def pop_pending_plan(self):
        """取出待执行的计划（由 Agent 调用）"""
        plan = self._pending_plan
        self._pending_plan = None
        return plan
