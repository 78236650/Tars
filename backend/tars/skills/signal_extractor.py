"""Lightweight intent/keyword extraction for SkillRouter — v4.1.0"""
import re
from typing import List, Tuple


_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}")


def extract_signals(text: str) -> Tuple[str, List[str], List[str]]:
    """Return (intent, entities, keywords) from user message."""
    if not text:
        return "general.chat", [], []

    intent = _detect_intent(text)
    keywords = _extract_keywords(text)
    entities = _extract_entities(text, keywords)
    return intent, entities, keywords


def _detect_intent(text: str) -> str:
    lower = text.lower()
    rules = [
        (["pdf", "文档", "提取", "表格"], "document.process"),
        (["github", "pr", "pull request", "ci", "workflow"], "devops.github"),
        (["excel", "xlsx", "表格", "spreadsheet"], "data.spreadsheet"),
        (["代码", "编程", "debug", "bug", "code"], "coding.explain"),
        (["摘要", "总结", "summary", "summarize"], "writing.summarize"),
        (["翻译", "translate"], "writing.translate"),
        (["计划", "规划", "plan", "任务分解"], "planning.task"),
        (["skill", "技能"], "skill.discovery"),
        (["计算", "算", "math", "calculate"], "data.analyze"),
        (["会议", "纪要", "meeting"], "meeting.notes"),
        (["搜索", "search", "查找"], "research.search"),
    ]
    for kws, intent in rules:
        if any(kw in lower or kw in text for kw in kws):
            return intent
    return "general.chat"


def _extract_keywords(text: str) -> List[str]:
    keywords: List[str] = []
    seen = set()

    for m in _CJK_RE.findall(text):
        if m not in seen:
            keywords.append(m)
            seen.add(m)

    for m in _WORD_RE.findall(text):
        w = m.lower()
        if len(w) >= 2 and w not in seen:
            keywords.append(w)
            seen.add(w)

    return keywords[:20]


def _extract_entities(text: str, keywords: List[str]) -> List[str]:
    entities = []
    for kw in keywords:
        if len(kw) >= 3:
            entities.append(kw)
    return entities[:10]
