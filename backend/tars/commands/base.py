"""斜杠命令基类"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class CommandResult:
    """命令执行结果"""
    prompt_injection: str = ""
    frontend_message: str = ""
    action: Optional[str] = None
    action_params: Dict[str, Any] = field(default_factory=dict)


class Command:
    def __init__(self, name: str, description: str, usage: str = ""):
        self.name = name
        self.description = description
        self.usage = usage or f"/{name}"

    def execute(self, args: str) -> CommandResult:
        raise NotImplementedError
