"""TARS 斜杠命令系统"""
from .base import Command, CommandResult
from .registry import CommandRegistry
from .parser import CommandParser

__all__ = ["Command", "CommandResult", "CommandRegistry", "CommandParser"]
