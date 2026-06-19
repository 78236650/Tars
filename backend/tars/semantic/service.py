"""Semantic layer business logic."""
from __future__ import annotations

import re

from .catalog import PORT_GLOSSARY_SEED
from .models import GlossaryTerm, FieldSemantic
from .repository import SemanticRepository


class SemanticService:
    def __init__(self, repo: SemanticRepository):
        self.repo = repo

    def seed_glossary_if_empty(self, user_id: str = "default") -> int:
        """Insert port glossary seed terms when catalog is empty for user."""
        if self.repo.count_terms(user_id=user_id) > 0:
            return 0
        count = 0
        for entry in PORT_GLOSSARY_SEED:
            self.repo.create_term(
                term=entry["term"],
                definition=entry["definition"],
                domain=entry.get("domain", "port"),
                aliases=entry.get("aliases", []),
                user_id=user_id,
            )
            count += 1
        return count

    def list_terms(self, *, domain: str | None = None, user_id: str = "default") -> list[GlossaryTerm]:
        return self.repo.list_terms(domain=domain, user_id=user_id)

    def create_term(
        self,
        *,
        term: str,
        definition: str,
        domain: str = "port",
        aliases: list[str] | None = None,
        user_id: str = "default",
    ) -> GlossaryTerm:
        return self.repo.create_term(
            term=term, definition=definition, domain=domain,
            aliases=aliases, user_id=user_id,
        )

    def delete_term(self, term_id: str, user_id: str = "default") -> bool:
        return self.repo.delete_term(term_id, user_id=user_id)

    def list_field_semantics(
        self,
        datasource_id: str,
        *,
        table_name: str | None = None,
        status: str | None = None,
        user_id: str = "default",
    ) -> list[FieldSemantic]:
        return self.repo.list_field_semantics(
            datasource_id, table_name=table_name, status=status, user_id=user_id,
        )

    def suggest_from_columns(
        self,
        datasource_id: str,
        table_name: str,
        columns: list[str],
        *,
        user_id: str = "default",
    ) -> list[FieldSemantic]:
        """Match column names to glossary terms heuristically."""
        terms = self.repo.list_terms(user_id=user_id)
        if not terms:
            self.seed_glossary_if_empty(user_id=user_id)
            terms = self.repo.list_terms(user_id=user_id)

        existing = {
            f.column_name.lower()
            for f in self.repo.list_field_semantics(datasource_id, table_name=table_name, user_id=user_id)
        }
        created: list[FieldSemantic] = []
        for col in columns:
            if col.lower() in existing:
                continue
            match = self._match_column(col, terms)
            if match:
                term, confidence = match
                fs = self.repo.create_field_semantic(
                    datasource_id=datasource_id,
                    table_name=table_name,
                    column_name=col,
                    term_id=term.id,
                    suggested_term=term.term,
                    confidence=confidence,
                    status="suggested",
                    user_id=user_id,
                )
                created.append(fs)
        return created

    def confirm_binding(
        self,
        field_id: str,
        *,
        term_id: str,
        user_id: str = "default",
    ) -> FieldSemantic | None:
        return self.repo.confirm_field_semantic(field_id, term_id=term_id, user_id=user_id)

    def lookup_for_question(self, question: str, user_id: str = "default") -> list[GlossaryTerm]:
        """Simple glossary lookup for MetricQaEngine RAG enhancement."""
        terms = self.repo.list_terms(user_id=user_id)
        hits: list[GlossaryTerm] = []
        q = question.lower()
        for t in terms:
            names = [t.term.lower()] + [a.lower() for a in t.aliases]
            if any(n in q for n in names):
                hits.append(t)
        return hits

    @staticmethod
    def _match_column(col: str, terms: list[GlossaryTerm]) -> tuple[GlossaryTerm, float] | None:
        col_norm = re.sub(r"[_\-\s]", "", col.lower())
        best: tuple[GlossaryTerm, float] | None = None
        for t in terms:
            candidates = [t.term] + t.aliases
            for name in candidates:
                name_norm = re.sub(r"[_\-\s]", "", name.lower())
                if name_norm in col_norm or col_norm in name_norm:
                    score = len(name_norm) / max(len(col_norm), 1)
                    if best is None or score > best[1]:
                        best = (t, min(score, 1.0))
        return best
