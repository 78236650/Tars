"""Shared data spine models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ResultSet:
    rows: list[list[Any]]
    column_names: list[str]
    truncated: bool = False
