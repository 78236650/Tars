"""报表数据模型 — TARS 风格 dataclass。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportChart:
    id: str
    datasource_id: str
    name: str = ""
    chart_type: str = "table"
    spec: dict = field(default_factory=dict)  # ChartSpec 序列化
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class Dashboard:
    id: str
    name: str = ""
    description: str = ""
    params: dict = field(default_factory=dict)  # global filters
    user_id: str = "default"
    created_at: str | None = None


@dataclass
class DashboardItem:
    id: str
    dashboard_id: str
    chart_id: str
    layout: dict = field(default_factory=lambda: {"x": 0, "y": 0, "w": 6, "h": 4})
    order: int = 0
