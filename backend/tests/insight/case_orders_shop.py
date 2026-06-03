"""Synthetic e-commerce orders datasource for InsightForge workflow tests.

Case narrative (订单电商):
  - Tables: orders, products
  - Approved metrics: gmv, order_count
  - Draft metric: gmv_draft
  - Typical questions: 昨日 GMV, 订单量, 新客占比 (adhoc/miss)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.store import InsightProfileRunStore
from tars.insight.workflow_service import InsightWorkflowService

USER_ID = "case-user-1"
# Per-user BI/Insight scope key (stored in legacy tenant_id columns).
TENANT = USER_ID
DS_NAME = "case_orders_shop"


@dataclass
class OrdersShopCase:
    db: Database
    datasource_id: str
    tenant_id: str
    session_id: str
    metric_ids: Dict[str, str]

    @property
    def headers(self) -> Dict[str, str]:
        return {"X-Tenant-ID": self.tenant_id}


def _schema_snapshot(workflow_state: str = "ready", **workflow_extra: Any) -> dict:
    workflow = {
        "state": workflow_state,
        "ins_version": "INS-2.0.0",
        **workflow_extra,
    }
    return {
        "tables": {
            "orders": {
                "columns": [
                    {"name": "id", "type": "bigint"},
                    {"name": "amount", "type": "decimal"},
                    {"name": "order_date", "type": "date"},
                    {"name": "user_id", "type": "bigint"},
                ],
            },
            "products": {
                "columns": [
                    {"name": "id", "type": "bigint"},
                    {"name": "name", "type": "varchar"},
                    {"name": "category", "type": "varchar"},
                ],
            },
        },
        "insight": {"workflow": workflow},
    }


def _insert_metric(
    db: Database,
    ds_id: str,
    tenant: str,
    key: str,
    sql: str,
    *,
    status: str = "approved",
    definition: Optional[str] = None,
) -> str:
    mid = str(uuid.uuid4())
    now = "2026-05-20T12:00:00"
    db._get_conn().execute(
        """
        INSERT INTO insight_metrics (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence, created_at, updated_at,
            version, superseded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '["orders"]', ?, 'profile', 0.92, ?, ?, 1, NULL)
        """,
        (
            mid,
            ds_id,
            tenant,
            key,
            key,
            definition or f"官方口径：{key}",
            sql,
            status,
            now,
            now,
        ),
    )
    db._get_conn().commit()
    return mid


def mock_sql_executor(_url: str, sql: str) -> dict:
    """Deterministic BI SQL results for case metrics."""
    upper = sql.upper()
    if "COUNT" in upper:
        return {
            "success": True,
            "data": [{"value": 42}],
            "columns": ["value"],
            "row_count": 1,
            "error": None,
            "sql": sql,
        }
    return {
        "success": True,
        "data": [{"value": 128800.5, "gmv": 128800.5}],
        "columns": ["value", "gmv"],
        "row_count": 1,
        "error": None,
        "sql": sql,
    }


async def route_hit_gmv(**_kwargs: Any) -> dict:
    return {
        "branch": "hit_approved",
        "metric_key": "gmv",
        "confidence": 0.95,
        "reasoning": "case: 昨日 GMV -> gmv",
    }


async def route_hit_partial(**_kwargs: Any) -> dict:
    return {
        "branch": "hit_partial",
        "confidence": 0.55,
        "open_questions": ["使用 gmv 还是 gmv_draft？"],
    }


async def route_adhoc(**_kwargs: Any) -> dict:
    return {"branch": "adhoc", "confidence": 0.35, "reasoning": "case: no metric"}


RouteFn = Callable[..., Awaitable[dict]]


def seed(
    db: Optional[Database] = None,
    *,
    workflow_state: str = "ready",
    workflow_extra: Optional[dict] = None,
    include_draft: bool = True,
) -> OrdersShopCase:
    """Seed in-memory DB with case datasource, session, and metrics."""
    database = db or Database(":memory:")
    bi = DataSourceStore(database)
    extra = dict(workflow_extra or {})
    ds = bi.create(
        TENANT,
        DS_NAME,
        "postgresql",
        "postgresql://localhost/case_orders",
        schema_snapshot=_schema_snapshot(workflow_state, **extra),
    )
    wf = InsightWorkflowService(database)
    if workflow_state != "needs_forge":
        wf.set_datasource_state(ds.id, TENANT, workflow_state)

    session = database.create_session(tenant_id=TENANT)
    wf.bind_session_datasource(session.id, TENANT, ds.id)

    metrics: Dict[str, str] = {}
    metrics["gmv"] = _insert_metric(
        database,
        ds.id,
        TENANT,
        "gmv",
        "SELECT COALESCE(SUM(amount), 0) AS value FROM orders WHERE order_date = :as_of_date",
        status="approved",
    )
    metrics["order_count"] = _insert_metric(
        database,
        ds.id,
        TENANT,
        "order_count",
        "SELECT COUNT(*) AS value FROM orders WHERE order_date = :as_of_date",
        status="approved",
    )
    if include_draft:
        metrics["gmv_draft"] = _insert_metric(
            database,
            ds.id,
            TENANT,
            "gmv_draft",
            "SELECT SUM(amount) AS value FROM orders",
            status="draft",
            definition="草稿 GMV（含退款前）",
        )

    return OrdersShopCase(
        db=database,
        datasource_id=ds.id,
        tenant_id=TENANT,
        session_id=session.id,
        metric_ids=metrics,
    )
