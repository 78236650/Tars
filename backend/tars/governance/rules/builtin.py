"""Builtin rules — 6 rule types for self-contained quality checks.

These are pure-function rules that work without Great Expectations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleResult:
    passed_count: int
    failed_count: int
    sample_violations: list[dict[str, Any]] = field(default_factory=list)


def validate_not_null(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check that a column has no null/empty values."""
    field = params["field"]
    try:
        col_idx = columns.index(field)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": f"Field '{field}' not found"}])

    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        val = row[col_idx] if col_idx < len(row) else None
        if val is None or (isinstance(val, str) and val.strip() == ""):
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "value": val})
        else:
            passed += 1

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


def validate_unique(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check that a column has unique values."""
    field = params["field"]
    try:
        col_idx = columns.index(field)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": f"Field '{field}' not found"}])

    seen: set[Any] = set()
    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        val = row[col_idx] if col_idx < len(row) else None
        if val in seen:
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "value": val})
        else:
            seen.add(val)
            passed += 1

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


def validate_range(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check that numeric values fall in [min, max]."""
    field = params["field"]
    mn = params.get("min")
    mx = params.get("max")
    try:
        col_idx = columns.index(field)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": f"Field '{field}' not found"}])

    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        val = row[col_idx] if col_idx < len(row) else None
        if val is None:
            passed += 1
            continue
        try:
            n = float(val)
            ok = True
            if mn is not None and n < mn:
                ok = False
            if mx is not None and n > mx:
                ok = False
            if ok:
                passed += 1
            else:
                failed += 1
                if len(violations) < 20:
                    violations.append({"row": i, "value": val})
        except (TypeError, ValueError):
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "value": val, "reason": "not numeric"})

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


def validate_regex(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check that values match a regex pattern."""
    field = params["field"]
    pattern = params["pattern"]
    try:
        col_idx = columns.index(field)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": f"Field '{field}' not found"}])

    rx = re.compile(pattern)
    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        val = row[col_idx] if col_idx < len(row) else None
        s = str(val) if val is not None else ""
        if rx.match(s):
            passed += 1
        else:
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "value": val})

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


def validate_enum(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check that values belong to an allowed set."""
    field = params["field"]
    values = set(params.get("values", []))
    try:
        col_idx = columns.index(field)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": f"Field '{field}' not found"}])

    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        val = row[col_idx] if col_idx < len(row) else None
        if val in values:
            passed += 1
        else:
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "value": val})

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


def validate_cross_field(rows: list[list[Any]], columns: list[str], params: dict) -> RuleResult:
    """Check cross-field consistency, e.g., start <= end."""
    left = params["left"]
    right = params["right"]
    op = params.get("op", "<=")

    try:
        li = columns.index(left)
        ri = columns.index(right)
    except ValueError:
        return RuleResult(passed_count=0, failed_count=0, sample_violations=[{"error": "Field not found"}])

    ops = {"<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
           ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
           "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    comparator = ops.get(op, ops["<="])

    passed = 0
    failed = 0
    violations: list[dict] = []
    for i, row in enumerate(rows):
        a = row[li] if li < len(row) else None
        b = row[ri] if ri < len(row) else None
        try:
            if comparator(a, b):
                passed += 1
            else:
                failed += 1
                if len(violations) < 20:
                    violations.append({"row": i, "left_value": a, "right_value": b, "op": op})
        except TypeError:
            failed += 1
            if len(violations) < 20:
                violations.append({"row": i, "left_value": a, "right_value": b, "op": op, "reason": "type error"})

    return RuleResult(passed_count=passed, failed_count=failed, sample_violations=violations)


# Registry
RULE_REGISTRY = {
    "not_null": validate_not_null,
    "unique": validate_unique,
    "range": validate_range,
    "regex": validate_regex,
    "enum": validate_enum,
    "cross_field": validate_cross_field,
}
