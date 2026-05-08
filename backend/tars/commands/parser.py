"""命令解析器"""
from typing import Optional, Tuple
from .registry import CommandRegistry
from .base import Command, CommandResult


class CommandParser:
    def __init__(self, registry: CommandRegistry):
        self.registry = registry

    def parse(self, text: str) -> Optional[Tuple[Command, str]]:
        text = text.strip()
        if not text.startswith("/"):
            return None
        parts = text[1:].split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        cmd = self.registry.get(name)
        return (cmd, args) if cmd else None

    def is_command(self, text: str) -> bool:
        return self.parse(text) is not None

    def execute(self, text: str) -> Optional[CommandResult]:
        parsed = self.parse(text)
        if not parsed:
            return None
        cmd, args = parsed
        return cmd.execute(args)
