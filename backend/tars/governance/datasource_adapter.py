"""Deprecated shim — use ``tars.data.spine`` instead."""
from __future__ import annotations

from ..data.models import ResultSet
from ..data.spine import fetch_rows

__all__ = ["ResultSet", "fetch_rows"]
