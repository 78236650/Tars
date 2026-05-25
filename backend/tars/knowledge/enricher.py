"""KnowledgeEnricher — v4.4 LLM 深度理解。"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.base import ChatMessage
from .enricher_prompts import build_enrich_prompt, build_map_prompt, build_reduce_prompt
from .metrics_extractor import enrich_metrics
from .models import (
    DocProfile,
    GlossaryItem,
    ParsedDocument,
    QAPair,
    SectionSummary,
)

logger = logging.getLogger(__name__)


_DEFAULT_CONFIG = {
    "enabled": True,
    "timeout_sec": 120,
    "max_input_chars": 48000,
    "json_repair_retries": 1,
    "synthetic_qa_max": 3,
    "glossary_max": 20,
    "key_facts_max": 30,
    "confidence_threshold": 0.6,
    "map_reduce_section_threshold": 8,
    "map_max_sections": 30,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_provider(tenant_id: str, llm_settings_store) -> tuple[Any, Dict[str, Any]]:
    try:
        from ..insight.llm_resolver import resolve_knowledge_llm

        resolved = resolve_knowledge_llm(tenant_id, llm_settings_store)
        if resolved.provider is None:
            logger.info(
                "[KnowledgeEnricher] tenant=%s no LLM (source=%s); configure Chat model",
                tenant_id,
                resolved.source,
            )
            return None, resolved.selection
        logger.debug(
            "[KnowledgeEnricher] tenant=%s using %s via %s",
            tenant_id,
            resolved.selection.get("label"),
            resolved.source,
        )
        return resolved.provider, resolved.selection
    except Exception as e:
        logger.warning("[KnowledgeEnricher] resolve provider failed: %s", e)
        return None, {}


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _extract_response_text(out: Any) -> str:
    if out is None:
        return ""
    if isinstance(out, str):
        return out
    if isinstance(out, dict):
        return str(out.get("content") or out.get("text") or out.get("output") or "")
    content = getattr(out, "content", None)
    if content is not None:
        return str(content)
    return str(out)


def _run_maybe_async(fn, *args, **kwargs) -> Any:
    result = fn(*args, **kwargs)
    if not inspect.iscoroutine(result):
        return result
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False
    if not in_loop:
        return asyncio.run(result)

    import concurrent.futures

    def _invoke_in_fresh_loop() -> Any:
        fresh = fn(*args, **kwargs)
        if inspect.iscoroutine(fresh):
            return asyncio.run(fresh)
        return fresh

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_invoke_in_fresh_loop).result()


def _llm_complete(provider, prompt: str) -> Optional[str]:
    if provider is None:
        return None
    messages = [ChatMessage(role="user", content=prompt)]
    for attr in ("complete", "generate", "chat"):
        fn = getattr(provider, attr, None)
        if not callable(fn):
            continue
        try:
            if attr == "chat":
                out = _run_maybe_async(fn, messages)
            else:
                out = _run_maybe_async(fn, prompt)
            text = _extract_response_text(out)
            if text:
                return text
        except Exception as e:
            logger.warning("[KnowledgeEnricher] LLM %s failed: %s", attr, e)
    return None


def _compute_confidence(
    parse_warnings: List[str],
    truncation_ratio: float,
    section_coverage: float,
    json_repair_used: bool,
) -> float:
    has_warnings = 1.0 if parse_warnings else 0.0
    candidates = [
        1.0 - 0.3 * has_warnings,
        1.0 - 0.4 * max(0.0, min(1.0, truncation_ratio)),
        max(0.0, min(1.0, section_coverage)),
        1.0 - (0.5 if json_repair_used else 0.0),
    ]
    return max(0.0, min(1.0, min(candidates)))


def _profile_from_data(
    data: Dict[str, Any],
    *,
    doc_id: str,
    doc_type: str,
    file_name: str,
    parsed: ParsedDocument,
    selection: Dict[str, Any],
    truncation_ratio: float,
    json_repair_used: bool,
    cfg: Dict[str, Any],
) -> DocProfile:
    sections_summary: List[SectionSummary] = []
    parsed_sections = parsed.sections or []
    section_summaries_by_id = {
        str(s.get("section_id") or ""): s
        for s in (data.get("sections") or [])
        if isinstance(s, dict)
    }
    for i, sec in enumerate(parsed_sections):
        sid = sec.section_id or f"s{i}"
        extra = section_summaries_by_id.get(sid) or {}
        sections_summary.append(
            SectionSummary(
                section_id=sid,
                title=sec.title,
                summary=str(extra.get("summary") or ""),
                key_facts=[str(x) for x in (extra.get("key_facts") or []) if x],
                page_or_slide=sec.page_or_slide,
            )
        )

    section_coverage = (
        1.0
        if not parsed_sections
        else min(1.0, len(sections_summary) / max(len(parsed_sections), 1))
    )

    return DocProfile(
        doc_id=doc_id,
        doc_type=doc_type or "generic",
        title=str(data.get("title") or "") or (file_name or doc_id),
        one_liner=str(data.get("one_liner") or "")[:160],
        summary=str(data.get("summary") or ""),
        key_points=[str(x) for x in (data.get("key_points") or []) if x],
        sections=sections_summary,
        key_facts=[str(x) for x in (data.get("key_facts") or []) if x][: int(cfg.get("key_facts_max", 30))],
        glossary=[
            GlossaryItem(term=str(g.get("term") or ""), definition=str(g.get("definition") or ""))
            for g in (data.get("glossary") or [])
            if isinstance(g, dict) and g.get("term")
        ][: int(cfg.get("glossary_max", 20))],
        qa_pairs=[
            QAPair(question=str(q.get("question") or ""), answer=str(q.get("answer") or ""))
            for q in (data.get("qa_pairs") or [])
            if isinstance(q, dict) and q.get("question")
        ][: int(cfg.get("synthetic_qa_max", 3))],
        tags=[str(t) for t in (data.get("tags") or []) if t],
        confidence=_compute_confidence(
            parse_warnings=parsed.parse_warnings,
            truncation_ratio=truncation_ratio,
            section_coverage=section_coverage,
            json_repair_used=json_repair_used,
        ),
        enriched_at=_now_iso(),
        model_id=str(selection.get("label") or selection.get("model") or "") or None,
        token_usage={},
        parse_warnings=list(parsed.parse_warnings or []),
    )


def _call_llm_json(
    provider,
    prompt: str,
    *,
    cfg: Dict[str, Any],
) -> tuple[Optional[Dict[str, Any]], bool]:
    raw = _llm_complete(provider, prompt)
    json_repair_used = False
    data = _extract_json(raw or "")
    if data is None and raw and cfg.get("json_repair_retries", 1) > 0:
        json_repair_used = True
        repair_prompt = prompt + "\n上次返回不是合法 JSON，请严格只输出 JSON。"
        raw2 = _llm_complete(provider, repair_prompt)
        data = _extract_json(raw2 or "")
    return data, json_repair_used


def _enrich_map_reduce(
    parsed: ParsedDocument,
    *,
    provider,
    doc_type: str,
    file_name: str,
    cfg: Dict[str, Any],
) -> tuple[Optional[Dict[str, Any]], bool]:
    sections = [s for s in (parsed.sections or []) if (s.text or "").strip()]
    if len(sections) > int(cfg.get("map_max_sections", 30)):
        parsed.parse_warnings.append("map_reduce_skipped: too_many_sections")
        return None, False

    map_parts: List[str] = []
    json_repair_used = False
    for sec in sections:
        prompt = build_map_prompt(
            section_title=sec.title,
            section_text=sec.text[:8000],
            doc_type=doc_type,
        )
        data, repaired = _call_llm_json(provider, prompt, cfg=cfg)
        json_repair_used = json_repair_used or repaired
        if not data:
            continue
        summary = data.get("section_summary") or data.get("summary") or ""
        facts = data.get("key_facts") or []
        map_parts.append(f"## {sec.title}\n{summary}\n关键事实: {facts}")

    if not map_parts:
        return None, json_repair_used

    reduce_prompt = build_reduce_prompt(
        doc_type=doc_type,
        file_name=file_name,
        map_results="\n\n".join(map_parts)[: int(cfg.get("max_input_chars", 48000))],
    )
    data, repaired = _call_llm_json(provider, reduce_prompt, cfg=cfg)
    return data, json_repair_used or repaired


def enrich_document(
    parsed: ParsedDocument,
    *,
    tenant_id: str,
    doc_id: str,
    doc_type: str,
    llm_settings_store=None,
    config: Optional[Dict[str, Any]] = None,
    file_name: str = "",
) -> Optional[DocProfile]:
    """生成 DocProfile；任何降级路径都返回 None（passage-only 路径仍可用）。"""
    cfg = dict(_DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    if not cfg.get("enabled", True):
        return None

    resolved_type = (doc_type or parsed.doc_type_hint or "generic").lower()

    # metrics 专路：结构化抽取，不走通用 prompt
    if resolved_type == "metrics" or (parsed.metrics_tables and not parsed.plain_text.strip()):
        profile = enrich_metrics(parsed, doc_id=doc_id, doc_type="metrics", file_name=file_name)
        if profile:
            profile.enriched_at = _now_iso()
        return profile

    provider, selection = _resolve_provider(tenant_id, llm_settings_store)
    if provider is None:
        logger.info("[KnowledgeEnricher] tenant=%s no provider, skip enrichment", tenant_id)
        return None

    text_len = len(parsed.plain_text or "")
    max_chars = int(cfg.get("max_input_chars", 48000))
    truncation_ratio = 0.0 if text_len <= max_chars else 1.0 - max_chars / max(text_len, 1)

    sections = [s for s in (parsed.sections or []) if (s.text or "").strip()]
    use_map_reduce = len(sections) >= int(cfg.get("map_reduce_section_threshold", 8))

    if use_map_reduce:
        data, json_repair_used = _enrich_map_reduce(
            parsed, provider=provider, doc_type=resolved_type, file_name=file_name, cfg=cfg
        )
    else:
        sample = (parsed.plain_text or "")[:max_chars]
        prompt = build_enrich_prompt(doc_type=resolved_type, sample=sample, file_name=file_name)
        data, json_repair_used = _call_llm_json(provider, prompt, cfg=cfg)

    if not data:
        logger.warning("[KnowledgeEnricher] LLM 输出无法解析为 JSON，doc=%s", doc_id)
        return None

    return _profile_from_data(
        data,
        doc_id=doc_id,
        doc_type=resolved_type,
        file_name=file_name,
        parsed=parsed,
        selection=selection,
        truncation_ratio=truncation_ratio,
        json_repair_used=json_repair_used,
        cfg=cfg,
    )
