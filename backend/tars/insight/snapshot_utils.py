"""Helpers for insight snapshot fields shown in workbench UI."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_LEGACY_LLM_PREFIXES = ("LLM 批次失败:", "未配置 LLM")


def format_llm_error(exc: Exception) -> str:
    msg = str(exc).strip()
    lower = msg.lower()
    if "403" in msg and "dashscope" in lower:
        return (
            "通义千问(DashScope) 鉴权失败(403)：请在「模型」页检查该端点的 API Key、"
            "模型是否已开通；修改后点击「用此模型重新建档」。"
        )
    if "401" in msg or "403" in msg:
        return (
            "大模型鉴权失败：请检查端点 API Key、模型名称与账号权限；"
            "修改后重新建档。"
        )
    if "429" in msg:
        return "大模型请求过于频繁(429)，请稍后重新建档。"
    if "timeout" in lower or "timed out" in lower:
        return "大模型请求超时，请检查网络或更换模型后重新建档。"
    m = re.search(r"Client error '(\d+)[^']*' for url '([^']+)'", msg)
    if m:
        code, url = m.group(1), m.group(2)
        host = url.split("/")[2] if "://" in url else url
        return f"大模型 HTTP {code}（{host}）：请检查端点配置与模型权限。"
    return f"大模型调用失败：{msg[:280]}"


def split_snapshot_questions(
    snapshot: Dict[str, Any],
) -> Tuple[List[str], List[str], str]:
    """
    Returns (open_questions, llm_errors, llm_status).
    Migrates legacy entries that were stored in open_questions.
    """
    open_questions = list(snapshot.get("open_questions") or [])
    llm_errors = list(snapshot.get("llm_errors") or [])
    llm_status = str(snapshot.get("llm_status") or "")

    legacy: List[str] = []
    business: List[str] = []
    for q in open_questions:
        if q.startswith("LLM 批次失败:"):
            legacy.append(q[len("LLM 批次失败:") :].strip() or q)
        elif q.startswith("未配置 LLM"):
            legacy.append(q)
        else:
            business.append(q)

    if legacy:
        for raw in legacy:
            if raw.startswith("Client error") or "HTTPStatusError" in raw:
                formatted = format_llm_error(Exception(raw))
            else:
                formatted = raw
            if formatted not in llm_errors:
                llm_errors.append(formatted)

    if not llm_status:
        if llm_errors:
            llm_status = "partial" if business or snapshot.get("tables") else "failed"
        else:
            llm_status = "ok"

    return business, llm_errors, llm_status
