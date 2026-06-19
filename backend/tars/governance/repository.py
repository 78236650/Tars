"""治理持久层 — raw-SQL CRUD (TARS Repository 模式)。"""
from __future__ import annotations

import json
import uuid

from ..database import Database
from .models import QualityRule, CheckRun, RuleResultRow


class GovernanceRepository:
    def __init__(self, db: Database):
        self.db = db

    # ── QualityRule ──────────────────────────────────────────

    def create_rule(
        self,
        *,
        datasource_id: str,
        kind: str,
        name: str = "",
        table_name: str = "",
        params: dict | None = None,
        engine: str = "builtin",
        user_id: str = "default",
    ) -> QualityRule:
        rid = str(uuid.uuid4())
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO quality_rules (id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, datetime('now'))""",
            (rid, name, datasource_id, table_name, kind,
             json.dumps(params or {}, ensure_ascii=False), engine, user_id),
        )
        conn.commit()
        return QualityRule(id=rid, datasource_id=datasource_id, kind=kind,
                          name=name, table_name=table_name, params=params or {},
                          engine=engine, user_id=user_id)

    def list_rules(
        self, datasource_id: str, *,
        table_name: str | None = None,
        user_id: str = "default",
    ) -> list[QualityRule]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        if table_name:
            cur.execute(
                "SELECT id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at "
                "FROM quality_rules WHERE datasource_id = ? AND table_name = ? AND user_id = ? "
                "ORDER BY created_at DESC",
                (datasource_id, table_name, user_id),
            )
        else:
            cur.execute(
                "SELECT id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at "
                "FROM quality_rules WHERE datasource_id = ? AND user_id = ? "
                "ORDER BY created_at DESC",
                (datasource_id, user_id),
            )
        return [self._row_to_rule(r) for r in cur.fetchall()]

    def get_rule(self, rule_id: str, user_id: str = "default") -> QualityRule | None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, datasource_id, table_name, kind, params, engine, enabled, user_id, created_at "
            "FROM quality_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        )
        r = cur.fetchone()
        return self._row_to_rule(r) if r else None

    def delete_rule(self, rule_id: str, user_id: str = "default") -> bool:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM quality_rules WHERE id = ? AND user_id = ?", (rule_id, user_id))
        conn.commit()
        return cur.rowcount > 0

    # ── CheckRun ─────────────────────────────────────────────

    def save_check_run(self, run: CheckRun, result_rows: list[RuleResultRow]) -> CheckRun:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO check_runs (id, datasource_id, table_name, status, total_rows, truncated, summary, error, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (run.id, run.datasource_id, run.table_name, run.status, run.total_rows,
             1 if run.truncated else 0, json.dumps(run.summary, ensure_ascii=False),
             run.error, run.user_id),
        )
        for rr in result_rows:
            cur.execute(
                """INSERT INTO rule_results (id, check_run_id, rule_id, rule_name, kind, engine, passed_count, failed_count, sample_violations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rr.id, rr.check_run_id, rr.rule_id, rr.rule_name, rr.kind, rr.engine,
                 rr.passed_count, rr.failed_count, json.dumps(rr.sample_violations, ensure_ascii=False)),
            )
        conn.commit()
        return run

    def get_check_run(self, run_id: str, user_id: str = "default") -> CheckRun | None:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            ("SELECT id, datasource_id, table_name, status, total_rows, truncated, summary, error, user_id, created_at "
             "FROM check_runs WHERE id = ? AND user_id = ?"),
            (run_id, user_id),
        )
        r = cur.fetchone()
        if not r:
            return None
        return CheckRun(
            id=r[0], datasource_id=r[1], table_name=r[2], status=r[3], total_rows=r[4],
            truncated=bool(r[5]), summary=json.loads(r[6] or "{}"), error=r[7],
            user_id=r[8], created_at=r[9],
        )

    # ── helpers ──────────────────────────────────────────────

    def _row_to_rule(self, row) -> QualityRule:
        return QualityRule(
            id=row[0], name=row[1] or "", datasource_id=row[2], table_name=row[3] or "",
            kind=row[4], params=json.loads(row[5] or "{}"), engine=row[6] or "builtin",
            enabled=bool(row[7]), user_id=row[8] or "default", created_at=row[9],
        )
