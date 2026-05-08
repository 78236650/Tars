"""命令注册表"""
from typing import Dict, Optional
from .base import Command


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, Command] = {}

    def register(self, cmd: Command):
        self._commands[cmd.name] = cmd

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def list_all(self) -> list:
        return list(self._commands.values())

    def list_names(self) -> list:
        return list(self._commands.keys())
