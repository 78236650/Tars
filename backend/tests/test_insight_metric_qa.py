"""MetricQaEngine and question log tests (INS-2.0)."""
import json
import time
import uuid

import pytest

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.metric_qa_engine import InsightQaError, MetricQaEngine
from tars.insight.question_log_store import InsightQuestionLogStore
from tars.insight.workflow_service import InsightWorkflowService


def _mock_sql(_url: str, sql: str):
    return {
        "success": True,
        "data": [{"value": 100, "gmv": 100}],
        "columns": ["value", "gmv"],
        "row_count": 1,
        "error": None,
        "sql": sql,
    }


def _insert_metric(db, ds_id: str, tenant: str, key: str, sql: str, status: str = "approved"):
    conn = db._get_conn()
    now = "2026-05-20T00:00:00"
    conn.execute(
        """
        INSERT INTO insight_metrics (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence, created_at, updated_at,
            version, superseded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, 'profile', 0.9, ?, ?, 1, NULL)
        """,
        (
            str(uuid.uuid4()),
            ds_id,
            tenant,
            key,
            key,
            f"def {key}",
            sql,
            status,
            now,
            now,
        ),
    )
    conn.commit()


@pytest.fixture
def qa_context():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "qa-ds", "sqlite", "sqlite:///:memory:")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "ready")
    _insert_metric(
        db,
        ds.id,
        "default",
        "gmv",
        "SELECT SUM(amount) AS value FROM orders",
        status="approved",
    )
    return db, ds


@pytest.mark.asyncio
async def test_hit_approved_fills_params_only(qa_context):
    db, ds = qa_context

    async def route(**_kwargs):
        return {
            "branch": "hit_approved",
            "metric_key": "gmv",
            "confidence": 0.9,
            "reasoning": "test",
        }

    engine = MetricQaEngine(db, route_fn=route, sql_executor=_mock_sql)
    ans = await engine.ask(ds.id, "default", "昨日 GMV")
    assert ans.branch == "hit_approved"
    assert ans.caliber_tier == "official"
    assert "SUM" in ans.sql.upper()
    assert ans.value == 100


def test_question_log_fewshot_token_cap():
    db = Database(":memory:")
    store = InsightQuestionLogStore(db)
    for i in range(10):
        store.insert_log(
            datasource_id="ds1",
            tenant_id="default",
            question=f"question {i} " + ("x" * 200),
            sql="SELECT 1",
            branch="hit_approved",
            outcome="success",
            caliber_tier="official",
            user_id="u1",
        )
    candidates = store.list_fewshot_candidates("ds1", "default", limit=20)
    selected = store.select_for_prompt(candidates, max_items=5, max_tokens=2000)
    assert len(selected) <= 5


def test_question_log_recall_timeout_returns_empty(monkeypatch):
    db = Database(":memory:")
    store = InsightQuestionLogStore(db)
    candidates = [{"question": f"q{i}", "sql": "SELECT 1"} for i in range(50)]
    tick = {"n": 0}

    def fake_perf():
        tick["n"] += 1
        return 0.0 if tick["n"] == 1 else 1.0

    monkeypatch.setattr(time, "perf_counter", fake_perf)
    selected = store.select_for_prompt(candidates, recall_timeout_ms=1)
    assert selected == []


@pytest.mark.asyncio
async def test_hit_partial_returns_candidates(qa_context):
    db, ds = qa_context
    _insert_metric(db, ds.id, "default", "orders", "SELECT COUNT(*) AS value FROM orders")

    async def route(**_kwargs):
        return {
            "branch": "hit_partial",
            "confidence": 0.5,
            "open_questions": ["选哪个?"],
        }

    engine = MetricQaEngine(db, route_fn=route, sql_executor=_mock_sql)
    ans = await engine.ask(ds.id, "default", "订单相关")
    assert ans.branch == "hit_partial"
    assert ans.candidates


@pytest.mark.asyncio
async def test_needs_forge_blocks_ask(qa_context):
    db, ds = qa_context
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "needs_forge")
    engine = MetricQaEngine(db, sql_executor=_mock_sql)
    with pytest.raises(InsightQaError) as exc:
        await engine.ask(ds.id, "default", "GMV")
    assert exc.value.code == "INSIGHT_NOT_PROFILED"
