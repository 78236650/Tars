"""Semantic layer API — /api/semantic"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...database import Database
from ...api._auth import require_module, require_authenticated_user, Principal
from ..repository import SemanticRepository
from ..service import SemanticService


router = APIRouter(prefix="/api/semantic", tags=["Semantic"])
router.dependencies = [Depends(require_module("semantic"))]

_db: Optional[Database] = None
_service: Optional[SemanticService] = None


def init_semantic_api(db: Database) -> None:
    global _db, _service
    _db = db
    repo = SemanticRepository(db)
    _service = SemanticService(repo)
    _service.seed_glossary_if_empty()


def _svc() -> SemanticService:
    if _service is None:
        raise HTTPException(503, "Semantic module not initialized")
    return _service


class TermCreate(BaseModel):
    term: str
    definition: str
    domain: str = "port"
    aliases: list[str] = []


class SuggestBody(BaseModel):
    datasource_id: str
    table_name: str
    columns: list[str]


class ConfirmBody(BaseModel):
    term_id: str


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "semantic"}


@router.get("/terms")
def list_terms(
    domain: str | None = None,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    terms = _svc().list_terms(domain=domain, user_id=principal.user_id)
    return {
        "terms": [
            {
                "id": t.id, "term": t.term, "definition": t.definition,
                "domain": t.domain, "aliases": t.aliases,
            }
            for t in terms
        ],
    }


@router.post("/terms")
def create_term(
    body: TermCreate,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    t = _svc().create_term(
        term=body.term, definition=body.definition, domain=body.domain,
        aliases=body.aliases, user_id=principal.user_id,
    )
    return {"id": t.id, "term": t.term, "definition": t.definition, "domain": t.domain}


@router.delete("/terms/{term_id}")
def delete_term(
    term_id: str,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    if not _svc().delete_term(term_id, user_id=principal.user_id):
        raise HTTPException(404, "术语不存在")
    return {"ok": True}


@router.get("/field-semantics")
def list_field_semantics(
    datasource_id: str,
    table_name: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    items = _svc().list_field_semantics(
        datasource_id, table_name=table_name, status=status, user_id=principal.user_id,
    )
    return {
        "items": [
            {
                "id": f.id, "datasource_id": f.datasource_id,
                "table_name": f.table_name, "column_name": f.column_name,
                "term_id": f.term_id, "suggested_term": f.suggested_term,
                "confidence": f.confidence, "status": f.status,
            }
            for f in items
        ],
    }


@router.post("/field-semantics/suggest")
def suggest_bindings(
    body: SuggestBody,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    created = _svc().suggest_from_columns(
        body.datasource_id, body.table_name, body.columns, user_id=principal.user_id,
    )
    return {"created": len(created), "items": [{"id": c.id, "column_name": c.column_name, "suggested_term": c.suggested_term} for c in created]}


@router.post("/field-semantics/{field_id}/confirm")
def confirm_binding(
    field_id: str,
    body: ConfirmBody,
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    fs = _svc().confirm_binding(field_id, term_id=body.term_id, user_id=principal.user_id)
    if fs is None:
        raise HTTPException(404, "字段绑定不存在")
    return {"id": fs.id, "status": fs.status, "term_id": fs.term_id}


@router.post("/lookup")
def lookup_terms(
    body: dict[str, Any],
    principal: Principal = Depends(require_authenticated_user),
) -> dict:
    question = str(body.get("question", ""))
    hits = _svc().lookup_for_question(question, user_id=principal.user_id)
    return {
        "terms": [{"term": t.term, "definition": t.definition} for t in hits],
    }
