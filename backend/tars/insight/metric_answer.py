"""MetricAnswer response model (INS-2.0)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MetricAnswerError:
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class MetricCitation:
    doc_id: str
    title: str
    snippet: str
    source_type: str  # insight_glossary | meeting_summary | metric_linked | document
    relevance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetricAnswer:
    value: Any = None
    unit: Optional[str] = None
    caliber_tier: str = "adhoc"
    metric_key: Optional[str] = None
    definition: str = ""
    sql: str = ""
    filters_summary: str = ""
    as_of: Optional[str] = None
    lag_seconds: Optional[int] = None
    confidence: float = 0.0
    branch: str = "rejected"
    reasoning: Optional[str] = None
    open_questions: List[str] = field(default_factory=list)
    candidates: List[str] = field(default_factory=list)
    error: Optional[MetricAnswerError] = None
    question_log_id: Optional[str] = None
    metric_id: Optional[str] = None
    citations: List[MetricCitation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.error:
            data["error"] = self.error.to_dict()
        else:
            data.pop("error", None)
        data["citations"] = [c.to_dict() for c in self.citations]
        return data
