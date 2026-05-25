"""知识库深度入库领域模型（v4.3.1）。

包含解析层 ParsedDocument、enrich 层 DocProfile、metrics 专路 MetricsTable。
所有模型支持 round-trip JSON 序列化，便于持久化与跨进程传输。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ----- 解析层 -----

@dataclass
class DocumentSection:
    section_id: str
    title: str
    level: int = 1
    text: str = ""
    page_or_slide: Optional[int] = None
    source_range: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentSection":
        return cls(
            section_id=str(data.get("section_id") or ""),
            title=str(data.get("title") or ""),
            level=int(data.get("level") or 1),
            text=str(data.get("text") or ""),
            page_or_slide=data.get("page_or_slide"),
            source_range=data.get("source_range"),
        )


@dataclass
class ParsedDocument:
    plain_text: str = ""
    sections: List[DocumentSection] = field(default_factory=list)
    doc_type_hint: str = "generic"
    parse_warnings: List[str] = field(default_factory=list)
    metrics_tables: List["MetricsTable"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plain_text": self.plain_text,
            "sections": [s.to_dict() for s in self.sections],
            "doc_type_hint": self.doc_type_hint,
            "parse_warnings": list(self.parse_warnings),
            "metrics_tables": [t.to_dict() for t in self.metrics_tables],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedDocument":
        return cls(
            plain_text=str(data.get("plain_text") or ""),
            sections=[DocumentSection.from_dict(s) for s in (data.get("sections") or [])],
            doc_type_hint=str(data.get("doc_type_hint") or "generic"),
            parse_warnings=list(data.get("parse_warnings") or []),
            metrics_tables=[MetricsTable.from_dict(t) for t in (data.get("metrics_tables") or [])],
        )


# ----- metrics 专路 -----

@dataclass
class MetricsTable:
    sheet_name: str
    headers: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    inferred_schema: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsTable":
        return cls(
            sheet_name=str(data.get("sheet_name") or ""),
            headers=list(data.get("headers") or []),
            rows=list(data.get("rows") or []),
            inferred_schema=dict(data.get("inferred_schema") or {}),
        )


# ----- enrich 层 -----

@dataclass
class SectionSummary:
    section_id: str
    title: str
    summary: str = ""
    key_facts: List[str] = field(default_factory=list)
    page_or_slide: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SectionSummary":
        return cls(
            section_id=str(data.get("section_id") or ""),
            title=str(data.get("title") or ""),
            summary=str(data.get("summary") or ""),
            key_facts=list(data.get("key_facts") or []),
            page_or_slide=data.get("page_or_slide"),
        )


@dataclass
class GlossaryItem:
    term: str
    definition: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlossaryItem":
        return cls(
            term=str(data.get("term") or ""),
            definition=str(data.get("definition") or ""),
        )


@dataclass
class QAPair:
    question: str
    answer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QAPair":
        return cls(
            question=str(data.get("question") or ""),
            answer=str(data.get("answer") or ""),
        )


@dataclass
class DocProfile:
    doc_id: str
    doc_type: str = "generic"
    title: str = ""
    one_liner: str = ""
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    sections: List[SectionSummary] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)
    glossary: List[GlossaryItem] = field(default_factory=list)
    qa_pairs: List[QAPair] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    enriched_at: Optional[str] = None
    model_id: Optional[str] = None
    token_usage: Dict[str, Any] = field(default_factory=dict)
    parse_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "one_liner": self.one_liner,
            "summary": self.summary,
            "key_points": list(self.key_points),
            "sections": [s.to_dict() for s in self.sections],
            "key_facts": list(self.key_facts),
            "glossary": [g.to_dict() for g in self.glossary],
            "qa_pairs": [q.to_dict() for q in self.qa_pairs],
            "tags": list(self.tags),
            "confidence": float(self.confidence),
            "enriched_at": self.enriched_at,
            "model_id": self.model_id,
            "token_usage": dict(self.token_usage or {}),
            "parse_warnings": list(self.parse_warnings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocProfile":
        return cls(
            doc_id=str(data.get("doc_id") or ""),
            doc_type=str(data.get("doc_type") or "generic"),
            title=str(data.get("title") or ""),
            one_liner=str(data.get("one_liner") or ""),
            summary=str(data.get("summary") or ""),
            key_points=list(data.get("key_points") or []),
            sections=[SectionSummary.from_dict(s) for s in (data.get("sections") or [])],
            key_facts=list(data.get("key_facts") or []),
            glossary=[GlossaryItem.from_dict(g) for g in (data.get("glossary") or [])],
            qa_pairs=[QAPair.from_dict(q) for q in (data.get("qa_pairs") or [])],
            tags=list(data.get("tags") or []),
            confidence=float(data.get("confidence") or 0.0),
            enriched_at=data.get("enriched_at"),
            model_id=data.get("model_id"),
            token_usage=dict(data.get("token_usage") or {}),
            parse_warnings=list(data.get("parse_warnings") or []),
        )


# ----- chunk_type 常量 -----

class ChunkType:
    DOC_SUMMARY = "doc_summary"
    SECTION_SUMMARY = "section_summary"
    KEY_FACT = "key_fact"
    SYNTHETIC_QA = "synthetic_qa"
    GLOSSARY = "glossary"
    PASSAGE = "passage"


DOC_TYPES = ("policy", "proposal", "metrics", "generic")
