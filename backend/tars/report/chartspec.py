"""ChartSpec — chart-library-agnostic semantic chart definition and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_CHART_CONSTRAINTS: dict[str, dict] = {
    "metric":       {"min_dimensions": 0, "max_dimensions": 0, "min_measures": 1, "max_measures": 1},
    "pie":          {"min_dimensions": 1, "max_dimensions": 1, "min_measures": 1, "max_measures": 1},
    "line":         {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "bar":          {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "area":         {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "stacked_bar":  {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "grouped_bar":  {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "table":        {"min_dimensions": 0, "max_dimensions": 99, "min_measures": 0, "max_measures": 99},
    "metric_trend": {"min_dimensions": 1, "max_dimensions": 1, "min_measures": 1, "max_measures": 1},
    "scatter":      {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "funnel":       {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 1},
    "heatmap":      {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 99},
    "radar":        {"min_dimensions": 0, "max_dimensions": 0, "min_measures": 3, "max_measures": 99},
    "gauge":        {"min_dimensions": 0, "max_dimensions": 0, "min_measures": 1, "max_measures": 1},
    "top_n":        {"min_dimensions": 1, "max_dimensions": 99, "min_measures": 1, "max_measures": 1},
}

VALID_CHART_TYPES = set(_CHART_CONSTRAINTS.keys())
VALID_AGGS = {"sum", "avg", "count", "min", "max", "count_distinct"}
VALID_OPS = {"==", "!=", "<", "<=", ">", ">=", "in"}


@dataclass
class DimensionSpec:
    field: str


@dataclass
class MeasureSpec:
    field: str
    agg: str


@dataclass
class FilterSpec:
    field: str
    op: str
    value: Any


@dataclass
class ChartSpec:
    chart_type: str
    dimensions: list[DimensionSpec] = field(default_factory=list)
    measures: list[MeasureSpec] = field(default_factory=list)
    filters: list[FilterSpec] = field(default_factory=list)
    limit: int = 100
    granularity: str | None = None

    def __post_init__(self):
        if self.chart_type not in VALID_CHART_TYPES:
            raise ValueError(f"Unknown chart type: {self.chart_type}")

    @classmethod
    def from_dict(cls, data: dict) -> ChartSpec:
        return cls(
            chart_type=data.get("chart_type", "table"),
            dimensions=[DimensionSpec(**d) for d in data.get("dimensions", [])],
            measures=[MeasureSpec(**m) for m in data.get("measures", [])],
            filters=[FilterSpec(**f) for f in data.get("filters", [])],
            limit=data.get("limit", 100),
            granularity=data.get("granularity"),
        )


def validate_spec(spec: ChartSpec, field_names: list[str], field_roles: dict[str, str]) -> list[str]:
    errors: list[str] = []
    constraints = _CHART_CONSTRAINTS.get(spec.chart_type)
    if constraints is None:
        return [f"Unknown chart type: {spec.chart_type}"]
    ndim = len(spec.dimensions)
    if ndim < constraints["min_dimensions"]:
        errors.append(f"Chart type '{spec.chart_type}' requires at least {constraints['min_dimensions']} dimension(s), got {ndim}")
    if ndim > constraints["max_dimensions"]:
        errors.append(f"Chart type '{spec.chart_type}' allows at most {constraints['max_dimensions']} dimension(s), got {ndim}")
    nmeas = len(spec.measures)
    if nmeas < constraints["min_measures"]:
        errors.append(f"Chart type '{spec.chart_type}' requires at least {constraints['min_measures']} measure(s), got {nmeas}")
    if nmeas > constraints["max_measures"]:
        errors.append(f"Chart type '{spec.chart_type}' allows at most {constraints['max_measures']} measure(s), got {nmeas}")
    for d in spec.dimensions:
        if d.field not in field_names:
            errors.append(f"Dimension field '{d.field}' not found in dataset")
    for m in spec.measures:
        if m.field not in field_names:
            errors.append(f"Measure field '{m.field}' not found in dataset")
        if m.agg not in VALID_AGGS:
            errors.append(f"Invalid aggregation '{m.agg}' for measure '{m.field}'")
    for f in spec.filters:
        if f.field not in field_names:
            errors.append(f"Filter field '{f.field}' not found in dataset")
        if f.op not in VALID_OPS:
            errors.append(f"Invalid filter operator '{f.op}' for field '{f.field}'")
    if spec.granularity and spec.granularity not in ("day", "week", "month", "quarter", "year"):
        errors.append(f"Invalid granularity: {spec.granularity}")
    return errors
