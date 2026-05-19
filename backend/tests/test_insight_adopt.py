"""Adoption and H3 feedback downgrade tests (INS-2.0 M4)."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tars.database import Database
from tars.database.bi_store import DataSourceStore
from tars.insight.adoption_service import AdoptionService
from tars.insight.question_log_store import InsightQuestionLogStore
from tars.insight.store import AdoptionConflictError, InsightMetricStore
from tars.insight.workflow_service import InsightWorkflowService


def _insert_metric(
    db,
    ds_id: str,
    tenant: str,
    key: str,
    *,
    status: str = "draft",
    definition: str = "def",
    sql: str = "SELECT 1 AS value",
    version: int = 1,
):
    mid = str(uuid.uuid4())
    now = "2026-05-20T00:00:00"
    db._get_conn().execute(
        """
        INSERT INTO insight_metrics (
            id, datasource_id, tenant_id, metric_key, display_name, definition,
            sql_template, tables_json, status, source, confidence, created_at, updated_at,
            version, superseded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, 'profile', 0.9, ?, ?, ?, NULL)
        """,
        (mid, ds_id, tenant, key, key, definition, sql, status, now, now, version),
    )
    db._get_conn().commit()
    return mid


@pytest.fixture
def adopt_ctx():
    db = Database(":memory:")
    bi = DataSourceStore(db)
    ds = bi.create("default", "adopt-ds", "sqlite", "sqlite:///:memory:")
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "ready")
    return db, ds


def test_adopt_draft_to_approved(adopt_ctx):
    db, ds = adopt_ctx
    mid = _insert_metric(db, ds.id, "default", "gmv", status="draft")
    svc = AdoptionService(db)
    result = svc.adopt(mid, "default", "user1")
    assert result["status"] == "approved"
    assert result["metric"]["status"] == "approved"


def test_adopt_idempotent_same_definition(adopt_ctx):
    db, ds = adopt_ctx
    mid = _insert_metric(
        db, ds.id, "default", "gmv", status="approved", definition="same"
    )
    store = InsightMetricStore(db)
    before = store.get_by_id(mid, "default")
    svc = AdoptionService(db)
    svc.adopt(mid, "default", "user1", definition="same")
    after = store.get_by_id(mid, "default")
    assert after.version == before.version
    assert after.status == "approved"


def test_adopt_bumps_version_on_definition_change(adopt_ctx):
    db, ds = adopt_ctx
    mid = _insert_metric(
        db, ds.id, "default", "gmv", status="approved", definition="v1"
    )
    svc = AdoptionService(db)
    result = svc.adopt(mid, "default", "user1", definition="v2")
    assert result["metric"]["version"] == 2
    old = InsightMetricStore(db).get_by_id(mid, "default")
    assert old.superseded_by == result["metric"]["id"]


def test_adopt_from_question_log(adopt_ctx):
    db, ds = adopt_ctx
    qlog = InsightQuestionLogStore(db)
    log_id = qlog.insert_log(
        datasource_id=ds.id,
        tenant_id="default",
        question="昨日 GMV",
        sql="SELECT 100 AS value",
        branch="adhoc",
        outcome="success",
        caliber_tier="adhoc",
        user_id="u1",
        metric_key="gmv_adhoc",
    )
    svc = AdoptionService(db)
    result = svc.adopt("", "default", "user1", question_log_id=log_id)
    assert result["status"] == "approved"
    assert result["metric"]["metric_key"] == "gmv_adhoc"


def test_h3_downgrade_after_feedback(adopt_ctx):
    db, ds = adopt_ctx
    mid = _insert_metric(
        db, ds.id, "default", "gmv", status="approved", definition="official"
    )
    qlog = InsightQuestionLogStore(db)
    svc = AdoptionService(db)
    for _ in range(3):
        lid = qlog.insert_log(
            datasource_id=ds.id,
            tenant_id="default",
            question="q",
            sql="SELECT 1",
            branch="hit_approved",
            outcome="success",
            caliber_tier="official",
            user_id="u1",
            metric_key="gmv",
        )
        qlog.update_feedback(lid, "default", -1)
        svc.process_feedback(lid, "default", -1, "u1")

    metric = InsightMetricStore(db).get_by_id(mid, "default")
    assert metric.status == "deprecated"


def test_pending_question_consumed_on_profile_complete(adopt_ctx):
    db, ds = adopt_ctx
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "forging")
    wf.set_pending_question(ds.id, "default", "昨日 GMV是多少", session_id="sess-1")
    pending = wf.transition_on_profile_complete(ds.id, "default")
    assert pending is not None
    assert pending.get("text")
    assert wf.get_composite(ds.id, "default").get("pending_question") is None


@pytest.mark.asyncio
async def test_job_runner_auto_ask_pending(adopt_ctx):
    db, ds = adopt_ctx
    from tars.insight.job_runner import InsightJobRunner

    runner = InsightJobRunner(db)
    wf = InsightWorkflowService(db)
    wf.set_datasource_state(ds.id, "default", "forging")
    wf.set_pending_question(ds.id, "default", "test question", session_id="s1")
    wf.transition_on_profile_complete(ds.id, "default")

    mock_answer = AsyncMock()
    with patch("tars.insight.metric_qa_engine.MetricQaEngine") as MockEngine:
        inst = MockEngine.return_value
        inst.ask = mock_answer
        await runner._auto_ask_pending(
            ds.id,
            "default",
            {"text": "test question", "session_id": "s1"},
        )
    mock_answer.assert_awaited_once()
    call_kw = mock_answer.await_args.kwargs
    assert call_kw.get("session_id") == "s1"
