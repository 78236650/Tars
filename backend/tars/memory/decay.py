"""Ebbinghaus 衰减评分"""
import math
from datetime import datetime, timezone, timedelta


def decay_score(similarity: float, importance: float, age_hours: float) -> float:
    """
    检索综合分 = 相似度 * 0.6 + 衰减 * 0.2 + 重要性 * 0.2
    importance 越高半衰期越长（importance=1 时半衰期 720h ≈ 30 天）。
    """
    importance = max(min(importance, 1.0), 0.0)
    half_life = max(importance, 0.1) * 720
    decay = math.exp(-max(age_hours, 0) / half_life)
    return similarity * 0.6 + decay * 0.2 + importance * 0.2


def hours_since(timestamp_iso: str) -> float:
    """计算 ISO 时间戳到现在的小时数；解析失败返回 0"""
    if not timestamp_iso:
        return 0.0
    try:
        ts = datetime.fromisoformat(timestamp_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone(timedelta(hours=8)))
        now = datetime.now(timezone(timedelta(hours=8)))
        return max((now - ts).total_seconds() / 3600, 0.0)
    except (ValueError, TypeError):
        return 0.0
