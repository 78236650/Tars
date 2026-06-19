"""Relative time range resolver — pure function, testable."""

from __future__ import annotations

from datetime import datetime, timedelta, date

PRESETS = {
    "last_7_days", "last_30_days", "last_90_days",
    "this_week", "this_month", "this_quarter", "this_year",
    "last_month", "last_quarter", "last_year",
}


def resolve_time_range(preset: str, now: datetime | date | None = None) -> tuple[str, str]:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {sorted(PRESETS)}")
    if now is None:
        now = date.today()
    if isinstance(now, datetime):
        now = now.date()

    if preset == "last_7_days":
        start, end = now - timedelta(days=7), now
    elif preset == "last_30_days":
        start, end = now - timedelta(days=30), now
    elif preset == "last_90_days":
        start, end = now - timedelta(days=90), now
    elif preset == "this_week":
        start, end = now - timedelta(days=now.weekday()), now
    elif preset == "this_month":
        start, end = now.replace(day=1), now
    elif preset == "this_quarter":
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start, end = now.replace(month=quarter_month, day=1), now
    elif preset == "this_year":
        start, end = now.replace(month=1, day=1), now
    elif preset == "last_month":
        first_of_this = now.replace(day=1)
        last_day_prev = first_of_this - timedelta(days=1)
        start, end = last_day_prev.replace(day=1), last_day_prev
    elif preset == "last_quarter":
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        first_of_this_quarter = now.replace(month=quarter_month, day=1)
        last_day_prev = first_of_this_quarter - timedelta(days=1)
        prev_quarter_month = ((last_day_prev.month - 1) // 3) * 3 + 1
        start = last_day_prev.replace(month=prev_quarter_month, day=1)
        end = last_day_prev
    elif preset == "last_year":
        start = now.replace(year=now.year - 1, month=1, day=1)
        end = now.replace(year=now.year - 1, month=12, day=31)
    else:
        start = end = now

    return (start.isoformat(), end.isoformat())
