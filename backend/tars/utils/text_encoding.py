"""Repair common UTF-8 mojibake from MySQL / legacy Latin-1 connections."""
from __future__ import annotations


def _cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def repair_mojibake(text: str) -> str:
    """Fix UTF-8 bytes mis-decoded as Latin-1 / CP1252 (e.g. MySQL without utf8mb4)."""
    if not text or _cjk_count(text) > 0:
        return text
    if not any(ord(ch) > 127 for ch in text):
        return text

    best = text
    best_cjk = _cjk_count(text)
    for encoding in ("latin-1", "cp1252"):
        try:
            fixed = text.encode(encoding).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
        cjk = _cjk_count(fixed)
        if cjk > best_cjk:
            best = fixed
            best_cjk = cjk
    return best
