"""报表持久层 — raw-SQL CRUD。"""
from __future__ import annotations

import json
import uuid

from ..database import Database
from .models import ReportChart, Dashboard, DashboardItem


class ReportRepository:
    def __init__(self, db: Database):
        self.db = db

    # ── Chart CRUD ──────────────────────────────────────────

    def create_chart(self, *, datasource_id: str, name: str, chart_type: str,
                     spec: dict, user_id: str = "default") -> ReportChart:
        cid = str(uuid.uuid4())
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO charts (id, name, datasource_id, chart_type, spec, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (cid, name, datasource_id, chart_type, json.dumps(spec, ensure_ascii=False), user_id),
        )
        conn.commit()
        return ReportChart(id=cid, datasource_id=datasource_id, name=name,
                          chart_type=chart_type, spec=spec, user_id=user_id)

    def list_charts(self, datasource_id: str, user_id: str = "default") -> list[ReportChart]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, datasource_id, chart_type, spec, user_id, created_at "
            "FROM charts WHERE datasource_id = ? AND user_id = ? ORDER BY created_at DESC",
            (datasource_id, user_id),
        )
        return [self._row_to_chart(r) for r in cur.fetchall()]

    def delete_chart(self, chart_id: str, user_id: str = "default") -> bool:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM charts WHERE id = ? AND user_id = ?", (chart_id, user_id))
        conn.commit()
        return cur.rowcount > 0

    # ── Dashboard CRUD ──────────────────────────────────────

    def create_dashboard(self, *, name: str, description: str = "",
                         params: dict | None = None,
                         user_id: str = "default") -> Dashboard:
        did = str(uuid.uuid4())
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dashboards (id, name, description, params, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (did, name, description, json.dumps(params or {}, ensure_ascii=False), user_id),
        )
        conn.commit()
        return Dashboard(id=did, name=name, description=description,
                        params=params or {}, user_id=user_id)

    def list_dashboards(self, user_id: str = "default") -> list[Dashboard]:
        conn = self.db._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, params, user_id, created_at "
            "FROM dashboards WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [Dashboard(id=r[0], name=r[1] or "", description=r[2] or "",
                         params=json.loads(r[3] or "{}"), user_id=r[4] or "default",
                         created_at=r[5]) for r in cur.fetchall()]

    def _row_to_chart(self, row) -> ReportChart:
        return ReportChart(
            id=row[0], name=row[1] or "", datasource_id=row[2],
            chart_type=row[3] or "table", spec=json.loads(row[4] or "{}"),
            user_id=row[5] or "default", created_at=row[6],
        )
