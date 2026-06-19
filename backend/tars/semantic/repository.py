"""Semantic layer persistence."""
from __future__ import annotations

import json
import uuid

from ..database import Database
from .models import GlossaryTerm, FieldSemantic


class SemanticRepository:
    def __init__(self, db: Database):
        self.db = db

    def create_term(
        self,
        *,
        term: str,
        definition: str,
        domain: str = "port",
        aliases: list[str] | None = None,
        user_id: str = "default",
    ) -> GlossaryTerm:
        tid = str(uuid.uuid4())
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO glossary_terms (id, term, definition, domain, aliases_json, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (tid, term, definition, domain, json.dumps(aliases or [], ensure_ascii=False), user_id),
        )
        conn.commit()
        return GlossaryTerm(
            id=tid, term=term, definition=definition, domain=domain,
            aliases=aliases or [], user_id=user_id,
        )

    def list_terms(
        self,
        *,
        domain: str | None = None,
        user_id: str = "default",
    ) -> list[GlossaryTerm]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        if domain:
            cur.execute(
                "SELECT id, term, definition, domain, aliases_json, user_id FROM glossary_terms "
                "WHERE user_id = ? AND domain = ? ORDER BY term",
                (user_id, domain),
            )
        else:
            cur.execute(
                "SELECT id, term, definition, domain, aliases_json, user_id FROM glossary_terms "
                "WHERE user_id = ? ORDER BY term",
                (user_id,),
            )
        return [self._row_term(r) for r in cur.fetchall()]

    def get_term(self, term_id: str, user_id: str = "default") -> GlossaryTerm | None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, term, definition, domain, aliases_json, user_id FROM glossary_terms "
            "WHERE id = ? AND user_id = ?",
            (term_id, user_id),
        )
        r = cur.fetchone()
        return self._row_term(r) if r else None

    def delete_term(self, term_id: str, user_id: str = "default") -> bool:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM glossary_terms WHERE id = ? AND user_id = ?", (term_id, user_id))
        conn.commit()
        return cur.rowcount > 0

    def count_terms(self, user_id: str = "default") -> int:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM glossary_terms WHERE user_id = ?", (user_id,))
        return cur.fetchone()[0]

    def create_field_semantic(
        self,
        *,
        datasource_id: str,
        table_name: str,
        column_name: str,
        term_id: str | None = None,
        suggested_term: str | None = None,
        confidence: float = 0.0,
        status: str = "suggested",
        user_id: str = "default",
    ) -> FieldSemantic:
        fid = str(uuid.uuid4())
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO field_semantics
               (id, datasource_id, table_name, column_name, term_id, suggested_term,
                confidence, status, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (fid, datasource_id, table_name, column_name, term_id, suggested_term,
             confidence, status, user_id),
        )
        conn.commit()
        return FieldSemantic(
            id=fid, datasource_id=datasource_id, table_name=table_name,
            column_name=column_name, term_id=term_id, suggested_term=suggested_term,
            confidence=confidence, status=status, user_id=user_id,
        )

    def list_field_semantics(
        self,
        datasource_id: str,
        *,
        table_name: str | None = None,
        status: str | None = None,
        user_id: str = "default",
    ) -> list[FieldSemantic]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        sql = (
            "SELECT id, datasource_id, table_name, column_name, term_id, suggested_term, "
            "confidence, status, user_id FROM field_semantics WHERE datasource_id = ? AND user_id = ?"
        )
        params: list = [datasource_id, user_id]
        if table_name:
            sql += " AND table_name = ?"
            params.append(table_name)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY table_name, column_name"
        cur.execute(sql, params)
        return [self._row_field(r) for r in cur.fetchall()]

    def confirm_field_semantic(
        self,
        field_id: str,
        *,
        term_id: str,
        user_id: str = "default",
    ) -> FieldSemantic | None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE field_semantics SET term_id = ?, status = 'confirmed' "
            "WHERE id = ? AND user_id = ?",
            (term_id, field_id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        cur.execute(
            "SELECT id, datasource_id, table_name, column_name, term_id, suggested_term, "
            "confidence, status, user_id FROM field_semantics WHERE id = ?",
            (field_id,),
        )
        r = cur.fetchone()
        return self._row_field(r) if r else None

    @staticmethod
    def _row_term(row) -> GlossaryTerm:
        aliases = json.loads(row[4]) if row[4] else []
        return GlossaryTerm(
            id=row[0], term=row[1], definition=row[2], domain=row[3],
            aliases=aliases, user_id=row[5],
        )

    @staticmethod
    def _row_field(row) -> FieldSemantic:
        return FieldSemantic(
            id=row[0], datasource_id=row[1], table_name=row[2], column_name=row[3],
            term_id=row[4], suggested_term=row[5], confidence=float(row[6] or 0),
            status=row[7], user_id=row[8],
        )
