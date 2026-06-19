"""Renderer — convert aggregated results to chart-library-neutral output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeriesItem:
    name: str
    data: list[Any]


@dataclass
class ChartData:
    categories: list[Any] = field(default_factory=list)
    series: list[SeriesItem] = field(default_factory=list)
    truncated: bool = False


def render(
    columns: list[str],
    rows: list[list[Any]],
    measures_count: int,
    truncated: bool = False,
) -> ChartData:
    if not rows:
        return ChartData(truncated=truncated)

    dim_count = len(columns) - measures_count
    categories: list[str] = []
    series_data: list[list[Any]] = [[] for _ in range(measures_count)]

    for row in rows:
        if dim_count == 0:
            cat = "Total"
        elif dim_count == 1:
            cat = str(row[0]) if row[0] is not None else ""
        else:
            parts = [str(r) if r is not None else "" for r in row[:dim_count]]
            cat = " / ".join(parts)
        categories.append(cat)
        for i in range(measures_count):
            series_data[i].append(row[dim_count + i])

    series = []
    for i in range(measures_count):
        name = columns[dim_count + i] if dim_count + i < len(columns) else f"measure_{i}"
        series.append(SeriesItem(name=name, data=series_data[i]))

    return ChartData(categories=categories, series=series, truncated=truncated)
