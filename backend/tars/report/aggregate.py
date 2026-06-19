"""Aggregation engine — pure functions for grouping and aggregating ResultSets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .chartspec import ChartSpec

VALID_GRANULARITIES = {"day", "week", "month", "quarter", "year"}


@dataclass
class AggregatedResult:
    columns: list[str]
    rows: list[list[Any]]


def aggregate(
    rows: list[list[Any]],
    column_names: list[str],
    spec: ChartSpec,
) -> AggregatedResult:
    filtered = _apply_filters(rows, column_names, spec.filters)
    dim_indices = [_idx(column_names, d.field) for d in spec.dimensions]
    meas_indices = [_idx(column_names, m.field) for m in spec.measures]
    groups: dict[tuple, dict] = {}
    for row in filtered:
        dim_vals: list[Any] = []
        for dim_idx in dim_indices:
            val = row[dim_idx] if dim_idx is not None else None
            val = _apply_granularity(val, spec.granularity)
            dim_vals.append(val)
        key = tuple(dim_vals)
        if key not in groups:
            groups[key] = {"_raw": [[] for _ in spec.measures]}
        for i in range(len(spec.measures)):
            meas_idx = meas_indices[i]
            if meas_idx is not None:
                val = row[meas_idx]
                if val is not None:
                    groups[key]["_raw"][i].append(val)
    result_rows: list[list[Any]] = []
    for key, group_data in sorted(groups.items()):
        row_out: list[Any] = list(key)
        for i, m in enumerate(spec.measures):
            raw_vals = group_data["_raw"][i]
            agg_val = _compute_agg(raw_vals, m.agg)
            row_out.append(agg_val)
        result_rows.append(row_out)
    dim_names = [d.field for d in spec.dimensions]
    meas_names = [f"{m.agg}({m.field})" for m in spec.measures]
    all_names = dim_names + meas_names
    if spec.limit and len(result_rows) > spec.limit:
        result_rows = result_rows[:spec.limit]
    return AggregatedResult(columns=all_names, rows=result_rows)


def _apply_filters(rows, column_names, filters):
    result = rows
    for f in filters:
        try:
            idx = column_names.index(f.field)
        except ValueError:
            continue
        filtered = []
        for row in result:
            val = row[idx]
            try:
                if _match_filter(val, f.op, f.value):
                    filtered.append(row)
            except (TypeError, ValueError):
                continue
        result = filtered
    return result


def _match_filter(val, op, target):
    if val is None:
        return False
    if op == "==": return val == target
    if op == "!=": return val != target
    if op == "<": return val < target
    if op == "<=": return val <= target
    if op == ">": return val > target
    if op == ">=": return val >= target
    if op == "in": return val in (target if isinstance(target, list) else [target])
    return True


def _compute_agg(values, agg):
    if not values: return None
    if agg == "sum": return sum(v for v in values if v is not None)
    if agg == "avg":
        clean = [v for v in values if v is not None]
        return sum(clean) / len(clean) if clean else None
    if agg == "count": return len(values)
    if agg == "count_distinct": return len(set(values))
    if agg == "min": return min(v for v in values if v is not None)
    if agg == "max": return max(v for v in values if v is not None)
    return values[0] if values else None


def _apply_granularity(val, granularity):
    if granularity is None or val is None:
        return val
    if granularity not in VALID_GRANULARITIES:
        return val
    import datetime
    try:
        if isinstance(val, str):
            val = datetime.date.fromisoformat(val)
    except (ValueError, TypeError):
        return val
    if not isinstance(val, (datetime.date, datetime.datetime)):
        return val
    if granularity == "day": return val
    if granularity == "week": return val - datetime.timedelta(days=val.weekday())
    if granularity == "month": return val.replace(day=1)
    if granularity == "quarter":
        quarter_month = ((val.month - 1) // 3) * 3 + 1
        return val.replace(month=quarter_month, day=1)
    if granularity == "year": return val.replace(month=1, day=1)
    return val


def _idx(column_names, field):
    try:
        return column_names.index(field)
    except ValueError:
        return None
