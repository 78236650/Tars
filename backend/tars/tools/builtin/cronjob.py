"""定时任务管理工具"""
import json
from typing import Any, Dict

from ..base import BaseTool, ToolResult


class CronJobTool(BaseTool):
    name: str = "cronjob"
    description: str = "管理定时任务，支持创建、查询、更新、删除、启用/禁用。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "get", "update", "delete", "enable", "disable"],
                "description": "操作类型",
            },
            "name": {"type": "string", "description": "任务名称"},
            "description": {"type": "string", "description": "任务描述"},
            "cron": {"type": "string", "description": "Cron 表达式（分 时 日 月 周）"},
            "task_type": {"type": "string", "description": "任务类型: reminder/delegate/prompt"},
            "task_config": {"type": "object", "description": "任务配置"},
            "id": {"type": "string", "description": "任务ID"},
        },
        "required": ["action"],
    }

    def __init__(self, db=None, cron_runtime=None):
        self.db = db
        self.cron_runtime = cron_runtime

    def set_runtime(self, cron_runtime):
        self.cron_runtime = cron_runtime

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")
        if not self.db:
            return ToolResult(success=False, output="", error="数据库未初始化")

        try:
            if action == "create":
                return await self._create(kwargs)
            elif action == "list":
                return await self._list(kwargs)
            elif action == "get":
                return await self._get(kwargs)
            elif action == "delete":
                return await self._delete(kwargs)
            elif action in ("enable", "disable"):
                return await self._toggle(kwargs, enabled=(action == "enable"))
            return ToolResult(success=False, output="", error=f"不支持的操作: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"操作失败: {e}")

    async def _create(self, args: Dict) -> ToolResult:
        name = args.get("name")
        cron = args.get("cron")
        if not name or not cron:
            return ToolResult(success=False, output="", error="名称和 cron 表达式不能为空")

        user_id = args.get("user_id", "default")
        task_type = args.get("task_type", "reminder")
        task_config_dict = dict(args.get("task_config", {}))
        if task_type == "reminder" and args.get("session_id") and "session_id" not in task_config_dict:
            task_config_dict["session_id"] = args["session_id"]
        task_config = json.dumps(task_config_dict)
        description = args.get("description")

        job = self.db.create_cronjob(
            user_id=user_id, name=name, cron_expression=cron,
            task_type=task_type, task_config=task_config, description=description,
        )
        if self.cron_runtime:
            await self.cron_runtime.sync_job(job.id)
        return ToolResult(
            success=True,
            output=f"定时任务 '{name}' 创建成功 (ID: {job.id})",
            metadata={"job_id": job.id, "cron": cron},
        )

    def _resolve_job(self, args: Dict):
        """根据 id 或 name 解析任务，返回 (job, error_msg)"""
        job_id = args.get("id")
        name = args.get("name")
        user_id = args.get("user_id", "default")

        if job_id:
            job = self.db.get_cronjob(job_id)
            if job:
                return job, None
            # id 可能是名称，尝试按名称查找
            jobs = self.db.get_user_cronjobs(user_id)
            for j in jobs:
                if j.name == job_id:
                    return j, None
            return None, "任务不存在"

        if name:
            jobs = self.db.get_user_cronjobs(user_id)
            for j in jobs:
                if j.name == name:
                    return j, None
            return None, f"未找到名为 '{name}' 的任务"

        return None, "请提供任务ID或任务名称"

    async def _list(self, args: Dict) -> ToolResult:
        user_id = args.get("user_id", "default")
        jobs = self.db.get_user_cronjobs(user_id)
        lines = [f"共 {len(jobs)} 个定时任务:"]
        for j in jobs:
            status = "启用" if j.enabled else "禁用"
            lines.append(f"  [{status}] {j.name} (ID: {j.id}) — {j.cron_expression}")
        return ToolResult(success=True, output="\n".join(lines), metadata={"total": len(jobs)})

    async def _get(self, args: Dict) -> ToolResult:
        job, error = self._resolve_job(args)
        if error:
            return ToolResult(success=False, output="", error=error)
        return ToolResult(
            success=True,
            output=f"任务: {job.name}\nID: {job.id}\nCron: {job.cron_expression}\n类型: {job.task_type}\n状态: {'启用' if job.enabled else '禁用'}",
            metadata={"id": job.id, "name": job.name},
        )

    async def _delete(self, args: Dict) -> ToolResult:
        job, error = self._resolve_job(args)
        if error:
            return ToolResult(success=False, output="", error=error)
        self.db.delete_cronjob(job.id)
        if self.cron_runtime:
            self.cron_runtime.unschedule_job(job.id)
        return ToolResult(success=True, output=f"定时任务 '{job.name}' 已删除")

    async def _toggle(self, args: Dict, enabled: bool) -> ToolResult:
        job, error = self._resolve_job(args)
        if error:
            return ToolResult(success=False, output="", error=error)
        self.db.update_cronjob(job.id, enabled=enabled)
        if self.cron_runtime:
            if enabled:
                await self.cron_runtime.sync_job(job.id)
            else:
                self.cron_runtime.unschedule_job(job.id)
        return ToolResult(success=True, output=f"定时任务 '{job.name}' 已{'启用' if enabled else '禁用'}")
