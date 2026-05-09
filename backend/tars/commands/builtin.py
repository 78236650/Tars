"""内置命令注册"""
from tars.commands.base import Command, CommandResult
from tars.commands.registry import CommandRegistry

HELP_TEXT = """## 可用命令

| 命令 | 说明 |
|------|------|
| `/plan <任务>` | 规划模式：分析拆解任务，不写代码 |
| `/yolo` | 执行模式：直接动手，快速实现 |
| `/brainstorm <主题>` | 头脑风暴：发散思维，不限可行性 |
| `/subagent <name> <任务>` | 委派子代理 (code/writing/data/research) |
| `/skill <技能名>` | 激活一个 PromptSkill |
| `/clear` | 清空对话，开启新会话 |
| `/help` | 显示本帮助"""


class PlanCommand(Command):
    def __init__(self):
        super().__init__("plan", "进入规划模式，分解任务不写代码", "/plan <任务描述>")

    def execute(self, args: str) -> CommandResult:
        task = args or "当前任务"
        return CommandResult(
            prompt_injection=f"## PLAN MODE\n分析拆解任务，禁止写代码。输出3-6步Markdown清单。\n任务：{task}",
            frontend_message=f"🟡 PLAN MODE — {task[:40]}",
        )


class YoloCommand(Command):
    def __init__(self):
        super().__init__("yolo", "进入执行模式，直接动手快速实现", "/yolo")

    def execute(self, args: str) -> CommandResult:
        return CommandResult(
            prompt_injection="## YOLO MODE\n直接动手实现，不犹豫。遇小问题自修，大问题报告。",
            frontend_message="🟢 YOLO MODE",
        )


class BrainstormCommand(Command):
    def __init__(self):
        super().__init__("brainstorm", "头脑风暴模式，发散思维探索方向", "/brainstorm <主题>")

    def execute(self, args: str) -> CommandResult:
        topic = args or "当前话题"
        return CommandResult(
            prompt_injection=f"## BRAINSTORM MODE\n发散思维，列5-10个方向，禁止写代码。\n主题：{topic}",
            frontend_message=f"💡 BRAINSTORM — {topic[:40]}",
        )


class SubagentCommand(Command):
    def __init__(self):
        super().__init__("subagent", "委派任务给子代理 (code/writing/data/research)", "/subagent <code|writing|data|research> <任务>")

    def execute(self, args: str) -> CommandResult:
        parts = args.split(maxsplit=1)
        name = parts[0].lower() if parts else ""
        task = parts[1] if len(parts) > 1 else ""
        valid = {"code", "writing", "data", "research"}
        if name not in valid:
            return CommandResult(
                frontend_message=f"❌ 无效子代理: {name}。可选: {', '.join(sorted(valid))}",
            )
        return CommandResult(
            frontend_message=f"🤖 委派给 {name} 子代理: {task[:50]}",
            action="invoke_subagent",
            action_params={"agent_type": name, "task": task},
        )


class SkillCommand(Command):
    def __init__(self):
        super().__init__("skill", "技能管理：激活/权限/撤销", "/skill [permissions|revoke] <技能名>")

    def execute(self, args: str) -> CommandResult:
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        # /skill permissions <id>
        if sub == "permissions":
            return CommandResult(
                frontend_message=f"🔐 查询技能权限...",
                action="skill_permissions",
                action_params={"skill_id": rest},
            )
        # /skill revoke <id> <perm>
        if sub == "revoke":
            rparts = rest.split(maxsplit=1)
            return CommandResult(
                frontend_message=f"🔓 撤销权限中...",
                action="skill_revoke",
                action_params={"skill_id": rparts[0] if rparts else "", "permission": rparts[1] if len(rparts) > 1 else ""},
            )
        # /skill off <id>
        if sub == "off":
            return CommandResult(
                frontend_message=f"🔕 技能 {rest} 已关闭",
                action="skill_disable",
                action_params={"skill_id": rest},
            )

        # 默认：激活技能
        skill_id = args.strip()
        if not skill_id:
            return CommandResult(frontend_message="用法: /skill [permissions|revoke] <技能名>\n例: /skill deploy\n    /skill permissions deploy\n    /skill revoke deploy shell")
        return CommandResult(
            frontend_message=f"⚡ 技能 {skill_id} 已激活",
            action="activate_skill",
            action_params={"skill_id": skill_id},
        )


class ClearCommand(Command):
    def __init__(self):
        super().__init__("clear", "清空对话，开启新会话", "/clear")

    def execute(self, args: str) -> CommandResult:
        return CommandResult(
            frontend_message="🆕 新对话已开启",
            action="new_session",
        )


class HelpCommand(Command):
    def __init__(self):
        super().__init__("help", "显示所有可用命令", "/help")

    def execute(self, args: str) -> CommandResult:
        return CommandResult(frontend_message=HELP_TEXT)


def register_all(registry: CommandRegistry):
    registry.register(PlanCommand())
    registry.register(YoloCommand())
    registry.register(BrainstormCommand())
    registry.register(SubagentCommand())
    registry.register(SkillCommand())
    registry.register(ClearCommand())
    registry.register(HelpCommand())
